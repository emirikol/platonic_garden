#!/bin/bash

PORT=${PORT:=/dev/cu.usbserial-210}

ESP_FIRMWARE_VERSION=ESP32_GENERIC-20250415-v1.25.0
wget "https://micropython.org/resources/firmware/$ESP_FIRMWARE_VERSION.bin"
esptool.py --port "$PORT" erase_flash
esptool.py --port "$PORT" --baud 460800 write_flash 0x1000 "$ESP_FIRMWARE_VERSION.bin"

sleep 2
./install_dependencies.sh
./deploy.sh

