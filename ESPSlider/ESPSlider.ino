/**
 * ESPSlider - Offline Image Slideshow for 7.5 inch V2 E-Paper
 *
 * Images are compiled in as PROGMEM arrays (see images.h).
 * Run gen_images.py to regenerate images.h from test_img/*.bin.
 *
 * Cycles through all images every INTERVAL_MS milliseconds.
 */

#include <SPI.h>
#include "epd_minimal.h"
#include "images.h"

#define INTERVAL_MS 3000

static int currentImage = 0;
static unsigned long lastChange = 0;

void displayImage(int index) {
    if (index < 0 || index >= IMAGE_COUNT)
        return;
    Serial.printf("Displaying image %d / %d (%u bytes)\n", index + 1, IMAGE_COUNT,
                  (unsigned)IMAGES[index].size);

    const uint8_t *data = IMAGES[index].data;
    size_t size = IMAGES[index].size;

    EPD_7in5_V2_init();
    for (size_t i = 0; i < size; i++)
        EPD_SendData(pgm_read_byte(data + i));
    EPD_7IN5_V2_Show();
}

void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.printf("\nESPSlider: %d images compiled in\n", IMAGE_COUNT);

    SPI.begin();
    SPI.setFrequency(4000000);
    pinMode(CS_PIN, OUTPUT);
    pinMode(RST_PIN, OUTPUT);
    pinMode(DC_PIN, OUTPUT);
    pinMode(BUSY_PIN, INPUT);

    displayImage(0);
    lastChange = millis();
}

void loop() {
    if (IMAGE_COUNT > 1 && millis() - lastChange >= INTERVAL_MS) {
        currentImage = (currentImage + 1) % IMAGE_COUNT;
        displayImage(currentImage);
        lastChange = millis();
    }
}
