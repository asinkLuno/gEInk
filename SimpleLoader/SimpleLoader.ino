/*
  Simple ESP8266 E-Paper Image Server
  For 800x480 black/white e-paper display (7.5 inch V2)
  Receives image data via HTTP POST and displays on e-paper

  Data format: each byte encoded as two characters 'a' to 'p' (0-15)
  Each POST data should end with 4-byte length + "LOAD"
*/

#include <ESP8266WiFi.h>
#include <WiFiClient.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>

// WiFi credentials - pass via build flags: -DWIFI_SSID=\"your_ssid\" -DWIFI_PASSWORD=\"your_password\"
#ifdef WIFI_SSID
const char* ssid = WIFI_SSID;
#else
const char* ssid = "";
#endif

#ifdef WIFI_PASSWORD
const char* password = WIFI_PASSWORD;
#else
const char* password = "";
#endif

ESP8266WebServer server(80);
IPAddress myIP;

// SPI pins for e-paper (same as Loader)
#define PIN_SPI_SCK  14
#define PIN_SPI_DIN  13
#define CS_PIN 15
#define RST_PIN 2
#define DC_PIN 4
#define BUSY_PIN 5

// Pin level definitions
#define LOW 0
#define HIGH 1
#define GPIO_PIN_SET 1
#define GPIO_PIN_RESET 0

// Total bytes needed for 800x480 monochrome (1 bit per pixel)
const int TOTAL_BYTES = 800 * 480 / 8; // 48000 bytes

// Global state
bool displayInitialized = false;
int bytesReceived = 0;

// Function prototypes
void GPIO_Mode(unsigned char GPIO_Pin, unsigned char Mode);
void EpdSpiTransferCallback(byte data);
void EPD_SendCommand(byte command);
void EPD_SendData(byte data);
void EPD_WaitUntilIdle();
void EPD_Reset();
void EPD_Send_1(byte c, byte v1);
void EPD_Send_2(byte c, byte v1, byte v2);
void EPD_Send_3(byte c, byte v1, byte v2, byte v3);
void EPD_Send_4(byte c, byte v1, byte v2, byte v3, byte v4);
void EPD_7in5_V2_Readbusy();
void EPD_7IN5_V2_Show();
int EPD_7in5_V2_init();
void EPD_loadImage();
void handleRoot();
void handleInit();
void handleUpload();
void handleShow();
void handleNotFound();

void setup() {
    Serial.begin(115200);
    WiFi.mode(WIFI_STA);

    // Optional: set static IP (uncomment and adjust if needed)
    // wifi_station_dhcpc_stop();
    // struct ip_info info;
    // IP4_ADDR(&info.ip, 192, 168, 31, 211);
    // IP4_ADDR(&info.gw, 192, 168, 31, 1);
    // IP4_ADDR(&info.netmask, 255, 255, 255, 0);
    // wifi_set_ip_info(STATION_IF, &info);

    WiFi.begin(ssid, password);

    // SPI initialization
    pinMode(PIN_SPI_SCK, OUTPUT);
    pinMode(PIN_SPI_DIN, OUTPUT);
    pinMode(CS_PIN, OUTPUT);
    pinMode(RST_PIN, OUTPUT);
    pinMode(DC_PIN, OUTPUT);
    pinMode(BUSY_PIN, INPUT);

    // Wait for WiFi connection
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    Serial.print("\r\nIP address: ");
    Serial.println(myIP = WiFi.localIP());

    if (MDNS.begin("esp8266-epd")) {
        Serial.println("MDNS responder started");
    }

    // HTTP server endpoints
    server.on("/", handleRoot);
    server.on("/init", handleInit);
    server.on("/upload", handleUpload);
    server.on("/show", handleShow);
    server.onNotFound(handleNotFound);

    server.begin();
    Serial.println("HTTP server started");
}

void loop() {
    server.handleClient();
}

// GPIO helper
void GPIO_Mode(unsigned char GPIO_Pin, unsigned char Mode) {
    if (Mode == 0) {
        pinMode(GPIO_Pin, INPUT);
    } else {
        pinMode(GPIO_Pin, OUTPUT);
    }
}

// Basic SPI transfer function (bit-banged)
void EpdSpiTransferCallback(byte data) {
    digitalWrite(CS_PIN, GPIO_PIN_RESET);

    for (int i = 0; i < 8; i++) {
        if ((data & 0x80) == 0) digitalWrite(PIN_SPI_DIN, GPIO_PIN_RESET);
        else digitalWrite(PIN_SPI_DIN, GPIO_PIN_SET);

        data <<= 1;
        digitalWrite(PIN_SPI_SCK, GPIO_PIN_SET);
        digitalWrite(PIN_SPI_SCK, GPIO_PIN_RESET);
    }

    digitalWrite(CS_PIN, GPIO_PIN_SET);
}

// EPD command/data sending
void EPD_SendCommand(byte command) {
    digitalWrite(DC_PIN, LOW);
    EpdSpiTransferCallback(command);
}

void EPD_SendData(byte data) {
    digitalWrite(DC_PIN, HIGH);
    EpdSpiTransferCallback(data);
}

void EPD_WaitUntilIdle() {
    while (digitalRead(BUSY_PIN) == 0) delay(100);
}

void EPD_Reset() {
    digitalWrite(RST_PIN, HIGH);
    delay(50);
    digitalWrite(RST_PIN, LOW);
    delay(5);
    digitalWrite(RST_PIN, HIGH);
    delay(50);
}

// Helper functions for sending commands with data
void EPD_Send_1(byte c, byte v1) {
    EPD_SendCommand(c);
    EPD_SendData(v1);
}

void EPD_Send_2(byte c, byte v1, byte v2) {
    EPD_SendCommand(c);
    EPD_SendData(v1);
    EPD_SendData(v2);
}

void EPD_Send_3(byte c, byte v1, byte v2, byte v3) {
    EPD_SendCommand(c);
    EPD_SendData(v1);
    EPD_SendData(v2);
    EPD_SendData(v3);
}

void EPD_Send_4(byte c, byte v1, byte v2, byte v3, byte v4) {
    EPD_SendCommand(c);
    EPD_SendData(v1);
    EPD_SendData(v2);
    EPD_SendData(v3);
    EPD_SendData(v4);
}

// 7.5 inch V2 display busy check
void EPD_7in5_V2_Readbusy() {
    Serial.print("\r\ne-Paper busy\r\n");
    do {
        delay(20);
    } while (!digitalRead(BUSY_PIN));
    delay(20);
    Serial.print("e-Paper busy release\r\n");
}

// Show and sleep function
void EPD_7IN5_V2_Show() {
    EPD_SendCommand(0x12); // DISPLAY REFRESH
    delay(100); // !!!The delay here is necessary, 200uS at least!!!

    // Enter sleep mode
    EPD_SendCommand(0x02); // power off
    EPD_7in5_V2_Readbusy();
    EPD_SendCommand(0x07); // deep sleep
    EPD_SendData(0xA5);
}

// Display initialization
int EPD_7in5_V2_init() {
    EPD_Reset();

    EPD_SendCommand(0x01); // POWER SETTING
    EPD_SendData(0x07);
    EPD_SendData(0x07); // VGH=20V,VGL=-20V
    EPD_SendData(0x3f); // VDH=15V
    EPD_SendData(0x3f); // VDL=-15V

    EPD_SendCommand(0x04); // POWER ON
    delay(100);
    EPD_7in5_V2_Readbusy();

    EPD_SendCommand(0x00); // PANNEL SETTING
    EPD_SendData(0x1F); // KW-3f KWR-2F BWROTP 0f BWOTP 1f

    EPD_SendCommand(0x61); // tres
    EPD_SendData(0x03); // source 800
    EPD_SendData(0x20);
    EPD_SendData(0x01); // gate 480
    EPD_SendData(0xE0);

    EPD_SendCommand(0x15);
    EPD_SendData(0x00);

    EPD_SendCommand(0x50); // VCOM AND DATA INTERVAL SETTING
    EPD_SendData(0x10);
    EPD_SendData(0x07);

    EPD_SendCommand(0x60); // TCON SETTING
    EPD_SendData(0x22);

    EPD_SendCommand(0x13); // Start data transmission
    return 0;
}

// Image data loading function (inverted for V2 display)
void EPD_loadImage() {
    Serial.print("\r\nLoading image data");
    int index = 0;
    String p = server.arg(0);

    // Get the length of the image data (excluding 4-byte length + "LOAD")
    int DataLength = p.length() - 8;

    // Enumerate all image data bytes (2 chars per byte)
    while (index < DataLength) {
        // Get current byte: two characters 'a'-'p' representing 0-15
        int value = ((int)p[index] - 'a') + (((int)p[index + 1] - 'a') << 4);

        // Write the byte into e-Paper's memory (inverted for V2 display)
        EPD_SendData(~(byte)value);

        index += 2;
    }

    bytesReceived += DataLength / 2; // 2 chars per byte
    Serial.print("\r\nLoaded " + String(DataLength / 2) + " bytes, total: " + String(bytesReceived));
}

// HTTP request handlers
void handleRoot() {
    String html = "<!DOCTYPE html><html><head><title>E-Paper Image Upload</title></head>";
    html += "<body><h1>E-Paper Image Upload</h1>";
    html += "<p>Display: 800x480 monochrome (7.5 inch V2)</p>";
    html += "<p>Status: " + String(displayInitialized ? "Initialized" : "Not initialized") + "</p>";
    html += "<p>Bytes received: " + String(bytesReceived) + " / " + String(TOTAL_BYTES) + "</p>";
    html += "<form action='/upload' method='POST'>";
    html += "<p>Image data (encoded as two chars per byte, a-p):</p>";
    html += "<textarea name='data' rows='10' cols='80' placeholder='Paste encoded data here...'></textarea><br>";
    html += "<input type='submit' value='Upload'></form>";
    html += "<p><a href='/init'>Initialize Display</a> | <a href='/show'>Show Image</a></p>";
    html += "<p>Use curl: curl -X POST -d 'data=...' http://" + myIP.toString() + "/upload</p>";
    html += "</body></html>";
    server.send(200, "text/html", html);
}

void handleInit() {
    if (!displayInitialized) {
        EPD_7in5_V2_init();
        displayInitialized = true;
        bytesReceived = 0;
        server.send(200, "text/plain", "Display initialized. Ready to receive data.");
    } else {
        server.send(200, "text/plain", "Display already initialized.");
    }
}

void handleUpload() {
    if (!displayInitialized) {
        server.send(400, "text/plain", "Display not initialized. Please call /init first");
        return;
    }

    if (server.hasArg("data")) {
        String p = server.arg("data");

        // Check if data ends with "LOAD" (like original loader)
        if (p.endsWith("LOAD")) {
            int index = p.length() - 8;
            int L = ((int)p[index] - 'a') + (((int)p[index + 1] - 'a') << 4) +
                    (((int)p[index + 2] - 'a') << 8) + (((int)p[index + 3] - 'a') << 12);

            if (L == (p.length() - 8)) {
                EPD_loadImage();
                server.send(200, "text/plain", "Data received. Total bytes: " + String(bytesReceived) + "/" + String(TOTAL_BYTES));
            } else {
                server.send(400, "text/plain", "Length mismatch. Expected: " + String(L) + " chars, got: " + String(p.length() - 8));
            }
        } else {
            server.send(400, "text/plain", "Data must end with LOAD marker");
        }
    } else {
        server.send(400, "text/plain", "No data parameter");
    }
}

void handleShow() {
    if (!displayInitialized) {
        server.send(400, "text/plain", "Display not initialized");
        return;
    }

    if (bytesReceived < TOTAL_BYTES) {
        server.send(400, "text/plain", "Incomplete data: " + String(bytesReceived) + " bytes, expected " + String(TOTAL_BYTES));
        return;
    }

    EPD_7IN5_V2_Show();
    displayInitialized = false;
    bytesReceived = 0;
    server.send(200, "text/plain", "Display refreshed. Display is now in sleep mode. Reset for next image.");
}

void handleNotFound() {
    String message = "File Not Found\n\n";
    message += "URI: ";
    message += server.uri();
    message += "\nMethod: ";
    message += (server.method() == HTTP_GET) ? "GET" : "POST";
    message += "\nArguments: ";
    message += server.args();
    message += "\n";
    for (uint8_t i = 0; i < server.args(); i++) {
        message += " " + server.argName(i) + ": " + server.arg(i) + "\n";
    }
    server.send(200, "text/plain", message);
}