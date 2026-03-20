/**
 * ESPSlider - WiFi Image Slideshow for 7.5 inch V2 E-Paper
 *
 * Images (.bin) are stored in LittleFS and uploaded via WiFi.
 * Displays images in alphabetical order, switching every 30 seconds.
 *
 * Build flags:
 *   -DWIFI_SSID=\"your_ssid\"
 *   -DWIFI_PASSWORD=\"your_password\"
 *
 * HTTP endpoints:
 *   POST /upload   multipart file upload (field: "file")
 *   GET  /list     JSON list of stored images
 *   GET  /delete?name=foo.bin
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <LittleFS.h>
#include "epd_minimal.h"

#ifndef WIFI_SSID
#define WIFI_SSID ""
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD ""
#endif

#define INTERVAL_MS 30000
#define MAX_IMAGES  64

ESP8266WebServer server(80);

static char imagePaths[MAX_IMAGES][32];
static int  imageCount  = 0;
static int  currentImage = 0;
static unsigned long lastChange = 0;

// ---- Image list ---------------------------------------------------------

void loadImageList() {
    imageCount = 0;
    Dir dir = LittleFS.openDir("/");
    while (dir.next() && imageCount < MAX_IMAGES) {
        String name = dir.fileName();
        if (name.endsWith(".bin"))
            ("/" + name).toCharArray(imagePaths[imageCount++], sizeof(imagePaths[0]));
    }
    // Bubble sort for deterministic order
    for (int i = 0; i < imageCount - 1; i++)
        for (int j = i + 1; j < imageCount; j++)
            if (strcmp(imagePaths[i], imagePaths[j]) > 0) {
                char tmp[32];
                strcpy(tmp, imagePaths[i]);
                strcpy(imagePaths[i], imagePaths[j]);
                strcpy(imagePaths[j], tmp);
            }
    Serial.printf("Images: %d\n", imageCount);
}

// ---- Display ------------------------------------------------------------

void displayImage(int index) {
    if (index < 0 || index >= imageCount) return;
    Serial.printf("Displaying %s\n", imagePaths[index]);

    File f = LittleFS.open(imagePaths[index], "r");
    if (!f) { Serial.println("Failed to open"); return; }

    EPD_7in5_V2_init();
    while (f.available()) EPD_SendData(f.read());
    f.close();
    EPD_7IN5_V2_Show();
}

// ---- HTTP handlers ------------------------------------------------------

static File uploadFile;

void handleUploadBody() {
    HTTPUpload& upload = server.upload();
    if (upload.status == UPLOAD_FILE_START) {
        String path = "/" + upload.filename;
        Serial.printf("Receiving: %s\n", path.c_str());
        uploadFile = LittleFS.open(path, "w");
    } else if (upload.status == UPLOAD_FILE_WRITE) {
        if (uploadFile) uploadFile.write(upload.buf, upload.currentSize);
    } else if (upload.status == UPLOAD_FILE_END) {
        if (uploadFile) {
            uploadFile.close();
            Serial.printf("Saved: %lu bytes\n", upload.totalSize);
            loadImageList();
        }
    }
}

void handleList() {
    String json = "[";
    for (int i = 0; i < imageCount; i++) {
        if (i > 0) json += ",";
        json += "\"" + String(imagePaths[i]).substring(1) + "\"";
    }
    json += "]";
    server.send(200, "application/json", json);
}

void handleDelete() {
    if (!server.hasArg("name")) { server.send(400, "text/plain", "Missing name"); return; }
    String path = "/" + server.arg("name");
    if (LittleFS.remove(path)) {
        loadImageList();
        server.send(200, "text/plain", "Deleted");
    } else {
        server.send(404, "text/plain", "Not found");
    }
}

// ---- Setup & Loop -------------------------------------------------------

void setup() {
    Serial.begin(115200);
    delay(1000);

    if (!LittleFS.begin()) { Serial.println("LittleFS mount failed"); return; }
    loadImageList();

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.print("WiFi");
    for (int i = 0; i < 50 && WiFi.status() != WL_CONNECTED; i++) {
        delay(200); Serial.print(".");
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());
        server.on("/upload", HTTP_POST,
            []() { server.send(200, "text/plain", "OK"); },
            handleUploadBody);
        server.on("/list",   HTTP_GET, handleList);
        server.on("/delete", HTTP_GET, handleDelete);
        server.begin();
    } else {
        Serial.println("\nNo WiFi, offline mode");
    }

    SPI.begin();
    SPI.setFrequency(4000000);
    pinMode(CS_PIN, OUTPUT);
    pinMode(RST_PIN, OUTPUT);
    pinMode(DC_PIN, OUTPUT);
    pinMode(BUSY_PIN, INPUT);

    if (imageCount > 0) displayImage(0);
}

void loop() {
    server.handleClient();

    if (imageCount > 1 && millis() - lastChange >= INTERVAL_MS) {
        currentImage = (currentImage + 1) % imageCount;
        displayImage(currentImage);
        lastChange = millis();
    }
}
