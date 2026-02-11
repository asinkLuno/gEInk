geink preprocess ./test_img 
# geink dither ./test_img -m floyd_steinberg
geink dither ./test_img -m jarvis_judice_ninke
# geink dither ./test_img -m stucki
geink convert ./test_img
arduino-cli compile --fqbn esp8266:esp8266:generic /home/guozr/CODE/gEInk/ESPSlider
arduino-cli upload -p /dev/ttyUSB0 --fqbn esp8266:esp8266:generic /home/guozr/CODE/gEInk/ESPSlider
