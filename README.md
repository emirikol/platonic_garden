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

## Creating New Animations

This section outlines how to add new custom animations to the project.

Animations are Python modules located in the `animations/` directory. The system automatically discovers and loads any valid animation module placed in this folder.

### The `animate()` Function

Each animation module must define an asynchronous function named `animate`. This function is the entry point for your animation logic.

The `animate` function must have the following signature:

```python
async def animate(
        np: neopixel.NeoPixel,
        leds_per_face: int,
        num_faces: int,
        layers: tuple[tuple[int, ...], ...],
        sensors_to_face: list[list[int]],
        face_to_sensors: list[list[int]],
        face_positions: list[list[float]],
        stop_event: asyncio.Event,
        state: SharedState
    ) -> None:
```

**Parameters:**

*   `np: neopixel.NeoPixel`: The NeoPixel object instance used to control the LEDs. You'll use this object's methods (e.g., `np.write()`, `np[i] = (r, g, b)`) to set LED colors.
*   `leds_per_face: int`: The number of LEDs present on each face of the 3D shape.
*   `num_faces: int`: The total number of faces on the 3D shape.
*   `layers: tuple[tuple[int, ...], ...]`: Describes the physical layering of faces. It's a tuple where each inner tuple contains the face IDs belonging to a specific layer. This can be used to create effects that propagate through layers.
*   `sensors_to_face: list[list[int]]`: A mapping from sensor ID to a list of face IDs. `sensors_to_face[sensor_id]` gives a list of faces associated with that sensor.
*   `face_to_sensors: list[list[int]]`: A mapping from face ID to a list of sensor IDs. `face_to_sensors[face_id]` gives a list of sensors located on that face.
*   `face_positions: list[list[float]]`: A list containing the 3D coordinates `[x, y, z]` for the center of each face. The order corresponds to face IDs.
*   `stop_event: asyncio.Event`: An `asyncio.Event` that signals when the animation should terminate. Your animation loop should periodically check `stop_event.is_set()` and exit gracefully if it's true.
*   `state: SharedState`: A shared state object allowing access to global data, such as sensor readings or commands from other parts of the system (e.g., `(await state.get()).get('distances')`).

### Animation Logic Structure

A typical `animate` function will have the following structure:

1.  **Initialization**: Set up any initial colors, variables, or states specific to your animation.
2.  **Main Loop**:
    ```python
    while not stop_event.is_set():
        # 0. (Optional) Record frame start time for consistent frame rate
        #    frame_start_ns = time.time_ns()

        # 1. (Optional) Read data from shared state
        #    current_state_data = await state.get()
        #    sensor_values = current_state_data.get('distances')

        # 2. Implement your animation logic:
        #    Calculate LED colors based on time, sensor data, positions, layers, etc.
        #    For example, to set the color of a specific face:
        #    from animations.utils import set_face_color
        #    set_face_color(np, leds_per_face, face_id, (red, green, blue))
        #    Or, to set individual LEDs on a face (more advanced):
        #    for i in range(leds_per_face):
        #        led_index = face_id * leds_per_face + i
        #        np[led_index] = (red, green, blue)


        # 3. Update LEDs:
        #    Call np.write() to apply the new colors to the physical LEDs.
        #    np.write()

        # 4. Frame Rate Control:
        #    Pause execution to maintain the desired frame rate.
        #    frame_duration_ms = ... # Desired frame time in milliseconds
        #    await asyncio.sleep_ms(frame_duration_ms)
        #    Or, for more precise timing considering computation time:
        #    elapsed_ms = (time.time_ns() - frame_start_ns) / 1_000_000
        #    await asyncio.sleep_ms(max(0, int(frame_duration_ms - elapsed_ms)))
    ```

### Steps to Create a New Animation:

1.  **Create a Python File**: Add a new `.py` file in the `animations/` directory (e.g., `my_new_animation.py`).
2.  **Define `animate` Function**: Implement the `animate` async function as described above with your custom logic.
3.  **Import Utilities (Optional)**: You can use helper functions, like `set_face_color` from `animations.utils`, to simplify setting colors for entire faces.
4.  **Run**: The main application (`main.py`) automatically discovers animation modules in the `animations` directory. Your new animation should become available for selection or can be forced via `force_animation.txt`.
5.  **Forcing an Animation (for Development)**: While developing a new animation, it's often useful to force it to run without needing to select it through other means (e.g., a web interface or other control mechanism). You can do this using the `force_animation.py` script.
    *   To force a specific animation (e.g., `my_new_animation`):
        ```bash
        python force_animation.py my_new_animation
        ```
        This will create a `force_animation.txt` file on the ESP32. The main application will read this file on startup and run the specified animation.
    *   To remove the forced animation and revert to the default behavior (cycling through animations or responding to the shared state):
        ```bash
        python force_animation.py --remove
        ```
        This deletes the `force_animation.txt` file from the ESP32.
    *   Remember to run `./deploy.sh` after creating your new animation file so that `force_animation.py` can find it and the main application can run it.

### Shape Data and `get_shape()`

The parameters like `leds_per_face`, `num_faces`, `layers`, `face_positions`, etc., are derived from JSON files in the `shapes/` directory (e.g., `cube.json`, `icosahedron.json`). The `get_shape()` function in `main.py` is responsible for parsing these JSON files and preparing this data for the `animate` function.

Each shape JSON file typically defines:
*   `led_per_face`: Number of LEDs on each face.
*   `faces`: An array of face objects. Each face object can specify:
    *   `sensors`: A list of sensor IDs associated with that face.
    *   `pos`: The `[x, y, z]` coordinates of the face's center.
    *   Other metadata that might be used by `get_layers()` or other parts of the system to define layers or connectivity.
*   `sensors`: The total number of sensors in the system.

The `get_shape()` function processes this raw data to compute `num_faces`, `layers_map` (which becomes `layers`), `sensors_to_face`, `face_to_sensors`, and `face_positions`.

### Animation Orchestration by `run_animations()`

The `run_animations()` async function in `main.py` manages the lifecycle of animations:
1.  It discovers all available animation modules in the `animations/` directory using `get_animations()` (which likely inspects the directory).
2.  It provides a mechanism to start a specific animation, creating an `asyncio.Task` for it and managing a `stop_event` for termination.
3.  It can switch between animations by signaling the current animation to stop (using its `stop_event`) and then starting a new one.
4.  It monitors the shared `state` for an `animation` key, allowing external requests to change the currently running animation.

By following this structure, your new animation will integrate seamlessly into the existing system.
