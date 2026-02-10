geink preprocess ./test_img 
geink dither ./test_img 
geink convert ./test_img
arduino-cli compile --fqbn esp8266:esp8266:generic /home/guozr/CODE/gEInk/ESPSlider
arduino-cli upload -p /dev/ttyUSB0 --fqbn esp8266:esp8266:generic /home/guozr/CODE/gEInk/ESPSlider
