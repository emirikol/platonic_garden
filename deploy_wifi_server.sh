#!/bin/bash

PORT=${PORT:=/dev/cu.usbserial-210}

./deploy.sh
sleep 2
mpremote connect "$PORT" cp wlan_main.py :main.py
mpremote connect "$PORT" reset
