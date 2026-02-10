/**
 * ESPSlider - Offline Image Slideshow for 7.5 inch V2 E-Paper
 *
 * Displays 5 pre-loaded images in rotation, switching every 30 seconds.
 * No WiFi or WebServer required - pure standalone operation.
 */

#include <pgmspace.h>
#include "image1.h"
#include "image2.h"
#include "image3.h"
#include "image4.h"
#include "image5.h"
#include "epd_minimal.h"

// Image information structure
struct ImageInfo {
    const uint8_t* data;
    size_t size;
};

// Image array (5 images) - stored in Flash
const ImageInfo images[] = {
    {image1_data, 96000},
    {image2_data, 96000},
    {image3_data, 96000},
    {image4_data, 96000},
    {image5_data, 96000},
};
const int IMAGE_COUNT = 5;

// Display a single image
void displayImage(int index) {
    if (index < 0 || index >= IMAGE_COUNT) {
        Serial.printf("Invalid image index: %d\n", index);
        return;
    }

    Serial.printf("Displaying image %d...\n", index + 1);

    // Initialize e-Paper
    EPD_7in5_V2_init();

    // Send image data
    const uint8_t* data = images[index].data;
    size_t size = images[index].size;

    // Progress indicator
    int progress = 0;
    unsigned long startTime = millis();

    for (size_t i = 0; i < size; i++) {
        // Read from Flash using pgm_read_byte_near
        EPD_SendData(pgm_read_byte_near(&data[i]));

        // Print progress every 10%
        if ((i * 10) / size > progress) {
            progress = (i * 10) / size;
            Serial.printf("%d%% ", progress * 10);
        }
    }
    Serial.println("100%");

    unsigned long elapsed = millis() - startTime;
    Serial.printf("Transfer time: %lu ms\n", elapsed);

    // Refresh display and enter sleep
    EPD_7IN5_V2_Show();

    Serial.printf("Image %d displayed successfully\n", index + 1);
}

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("\r\n=== ESPSlider Image Slideshow ===");
    Serial.println("7.5 inch V2 E-Paper Display");
    Serial.println("Images: 5");
    Serial.println("Interval: 30 seconds");
    Serial.println("====================================\r\n");

    // Initialize SPI pins
    pinMode(PIN_SPI_SCK, OUTPUT);
    pinMode(PIN_SPI_DIN, OUTPUT);
    pinMode(CS_PIN, OUTPUT);
    pinMode(RST_PIN, OUTPUT);
    pinMode(DC_PIN, OUTPUT);
    pinMode(BUSY_PIN, INPUT);

    // Display first image
    displayImage(0);
    Serial.println("\r\nReady. Starting slideshow...\r\n");
}

void loop() {
    static unsigned long lastChange = 0;
    static int currentImage = 0;

    // Check if it's time to switch images
    if (millis() - lastChange >= 30000) {  // 30 seconds
        currentImage = (currentImage + 1) % IMAGE_COUNT;
        displayImage(currentImage);
        lastChange = millis();
        Serial.println();
    }
}
