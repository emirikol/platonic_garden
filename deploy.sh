#!/bin/bash
rm -rf animations/__pycache__
PORT=${PORT:-/dev/cu.usbserial-210}

mpremote connect "$PORT" fs mkdir shapes
mpremote connect "$PORT" fs mkdir animations
mpremote connect "$PORT" cp shapes/* :shapes/
mpremote connect "$PORT" cp animations/* :animations/
mpremote connect "$PORT" cp wifi_consts.py :wifi_consts.py
mpremote connect "$PORT" cp utils.py :utils.py
mpremote connect "$PORT" cp wifi_client.py :wifi_client.py
mpremote connect "$PORT" cp read_sensor.py :read_sensor.py
mpremote connect "$PORT" cp VL53L0X.py :VL53L0X.py
mpremote connect "$PORT" cp main.py :main.py
mpremote connect "$PORT" reset
