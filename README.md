# Platonic Garden

## Pins on PCB are marked with JX
Some of the pins cannot be used
* J9: GPIO 35: ❌ Don't use - input‑only ADC pin; has no output driver.
* J8: GPIO 33: ✅ Use - 
* J7: GPIO 26: ✅ Use
* J6: GPIO 13: ✅ Use
* J2: GPIO 03: ❌ Don't use - UART0 RX for USB/serial; driving it breaks REPL/flash comms.
* J3: GPIO 18: ✅ Use
* J4: GPIO 05: ❌ Don't use - boot‑strapping pin that must be high; NeoPixel lows can trap the chip in bootloader.
* J5: GPIO 02: ❌ Don't use - boot‑strapping pin that must be high; any low at reset prevents normal boot.

## The environment
### Creating the environment
On mac:
```bash
brew install python@3.12
./create_environment
source .venv/bin/activate
```

### Specifying the Serial Port (PORT)

All scripts that interact with the ESP32 (e.g., `./burn.sh`, `./install_dependencies.sh`, `./deploy.sh`, and `python set_shape.py`) use the `PORT` environment variable to identify the serial port.

If this variable is not set, the scripts will default to `/dev/cu.usbserial-210`.

To specify a different port, you can set the variable before running a script:
```bash
PORT=/dev/tty.usbserial-XXXX ./burn.sh
```
Or, for `set_shape.py`:
```bash
PORT=/dev/tty.usbserial-XXXX python set_shape.py your_shape
```
Replace `/dev/tty.usbserial-XXXX` with your actual serial port.

### Burning the ESP32 for the 1st time
This installs micropython on the ESP32 and runs all the other shell scripts in order to install dependencies and deploy the code
```bash
./burn.sh
```

### Installing dependencies on esp32
If you added an esp32 dependency, add it to the end of the line in `install_dependencies.sh` and run
```bash
./install_dependencies.sh
```

### Deploying the code
If you added files that need to be deployed to the esp32, add it to `deploy.sh`.

Every time you change the code run
```bash
./depoy.sh
```

## Setting the Shape

To set the active platonic solid shape displayed by the installation, use the `set_shape.py` script. This script updates a configuration file on the ESP32, which the main program then reads to determine which shape to display.

### Usage

```bash
python set_shape.py <shape_name>
```

Where `<shape_name>` is the name of the shape file (without the `.json` extension) located in the `shapes/` directory.

For example, to set the shape to `cube`:
```bash
python set_shape.py cube
```

The script will:
1. Check if `shapes/<shape_name>.json` exists.
2. Create a `shape.txt` file with the `<shape_name>` on the ESP32.

You can specify the serial port using the `PORT` environment variable. If not set, it defaults to `/dev/cu.usbserial-210`.
Example:
```bash
PORT=/dev/tty.usbserial-XXXX python set_shape.py cube
```
