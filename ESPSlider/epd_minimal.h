/**
  ******************************************************************************
  * @file    epd_minimal.h
  * @brief   Minimal EPD driver for 7.5 inch V2 e-Paper
  *          Extracted from epd.h and epd7in5.h for offline image slideshow
  ******************************************************************************
*/

#ifndef EPD_MINIMAL_H
#define EPD_MINIMAL_H

#include <SPI.h>

/* SPI pin definition --------------------------------------------------------*/
// Pin definitions (ESP8266 Arduino core already defines PIN_SPI_SCK, etc.)
#ifndef PIN_SPI_SCK
#define PIN_SPI_SCK  14
#endif
#ifndef PIN_SPI_DIN
#define PIN_SPI_DIN  13
#endif
#define CS_PIN 15
#define RST_PIN 2
#define DC_PIN 4
#define BUSY_PIN 5

/* Pin level definition ------------------------------------------------------*/
// LOW/HIGH already defined by Arduino core
#define GPIO_PIN_SET 1
#define GPIO_PIN_RESET 0

/* Forward declarations -------------------------------------------------------*/
void EpdSpiTransferCallback(byte data);

/* Sending a byte as a command -----------------------------------------------*/
void EPD_SendCommand(byte command)
{
    digitalWrite(DC_PIN, LOW);
    EpdSpiTransferCallback(command);
}

/* Sending a byte as a data --------------------------------------------------*/
void EPD_SendData(byte data)
{
    digitalWrite(DC_PIN, HIGH);
    EpdSpiTransferCallback(data);
}

/* The procedure of sending a byte to e-Paper by SPI -------------------------*/
void EpdSpiTransferCallback(byte data)
{
    digitalWrite(CS_PIN, GPIO_PIN_RESET);

    for (int i = 0; i < 8; i++)
    {
        if ((data & 0x80) == 0) digitalWrite(PIN_SPI_DIN, GPIO_PIN_RESET);
        else                    digitalWrite(PIN_SPI_DIN, GPIO_PIN_SET);

        data <<= 1;
        digitalWrite(PIN_SPI_SCK, GPIO_PIN_SET);
        digitalWrite(PIN_SPI_SCK, GPIO_PIN_RESET);
    }

    digitalWrite(CS_PIN, GPIO_PIN_SET);
}

/* Hardware reset -------------------------------------------------------------*/
void EPD_Reset()
{
    digitalWrite(RST_PIN, GPIO_PIN_SET);
    delay(200);
    digitalWrite(RST_PIN, GPIO_PIN_RESET);
    delay(10);
    digitalWrite(RST_PIN, GPIO_PIN_SET);
    delay(200);
}

/* Waiting the e-Paper is ready -----------------------------------------------*/
static void EPD_7in5_V2_Readbusy(void)
{
    Serial.print("\r\ne-Paper busy\r\n");
    do{
        delay(20);
    }while(!(digitalRead(BUSY_PIN)));
    delay(20);
    Serial.print("e-Paper busy release\r\n");
}

/* Initialize 7.5 inch V2 e-Paper --------------------------------------------*/
int EPD_7in5_V2_init()
{
    EPD_Reset();

    EPD_SendCommand(0x01); //POWER SETTING
    EPD_SendData(0x07);
    EPD_SendData(0x07); //VGH=20V,VGL=-20V
    EPD_SendData(0x3f); //VDH=15V
    EPD_SendData(0x3f); //VDL=-15V

    EPD_SendCommand(0x04); //POWER ON
    delay(100);
    EPD_7in5_V2_Readbusy();

    EPD_SendCommand(0X00); //PANNEL SETTING
    EPD_SendData(0x1F);    //KW-3f   KWR-2F	BWROTP 0f	BWOTP 1f

    EPD_SendCommand(0x61); //tres
    EPD_SendData(0x03);    //source 800
    EPD_SendData(0x20);
    EPD_SendData(0x01); //gate 480
    EPD_SendData(0xE0);

    EPD_SendCommand(0X15);
    EPD_SendData(0x00);

    EPD_SendCommand(0X50); //VCOM AND DATA INTERVAL SETTING
    EPD_SendData(0x10);
    EPD_SendData(0x07);

    EPD_SendCommand(0X60); //TCON SETTING
    EPD_SendData(0x22);

    EPD_SendCommand(0x13); // Write new data to RAM
    return 0;
}

/* Display and enter sleep mode ----------------------------------------------*/
static void EPD_7IN5_V2_Show(void)
{
    EPD_SendCommand(0x12); //DISPLAY REFRESH
    delay(100);            //!!!The delay here is necessary, 200uS at least!!!

    //Enter sleep mode
    EPD_SendCommand(0X02); //power off
    EPD_7in5_V2_Readbusy();
    EPD_SendCommand(0X07); //deep sleep
    EPD_SendData(0xA5);
}

#endif // EPD_MINIMAL_H
