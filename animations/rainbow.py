import asyncio
import time
import math
from utils import SharedState
from shape import Shape

RAINBOW_COLORS = [
    (255, 0, 0), # Red
    (255, 127, 0), # Orange
    (255, 255, 0), # Yellow
    (0, 255, 0), # Green
    (0, 255, 255), # Cyan
    (0, 0, 255), # Blue
    (127, 0, 255), # Violet
]
COLOR_CHANGE_INTERVAL = 300
FRAME_TIME = 50

async def animate(
        shape: Shape,
        stop_event: asyncio.Event,
        state: SharedState
) -> None:
    # Initial fill with 0.5 brightness of the first rainbow color
    initial_base_color = RAINBOW_COLORS[0]
    initial_bright_color = tuple(int(c * 0.5) for c in initial_base_color)
    shape.fill(initial_bright_color)
    shape.write()
    
    current_color_index = 0
    last_color_sweep_time_ms = time.ticks_ms() 
    
    # Phase for brightness oscillation for each face (radians)
    face_phases = [0.0] * shape.num_faces 
    
    # Variables for the rainbow color sweep effect (which part of rainbow applies where)
    current_layer_for_sweep = 0
    current_face_in_layer_for_sweep = 0

    # Temperature thresholds and frequency scaling for pulsing
    TEMP_MIN_PULSE = 30      # Temp at which pulsing starts
    FREQ_HZ_MIN = 1/3        # Frequency (Hz) at TEMP_MIN_PULSE
    FREQ_HZ_MAX = 2.0        # Frequency (Hz) at TEMP_MAX_SENSOR_VAL
    TEMP_MAX_SENSOR_VAL = 255 # Max value for temperature from sensor (0-255 range)
    BASE_BRIGHTNESS = 0.5

    while not stop_event.is_set():
        frame_start_ms = time.ticks_ms()
        # Frame time delta in seconds, used for phase calculation
        dt_seconds = FRAME_TIME / 1000.0 

        # Get sensor data (list of (distance, temperature) tuples)
        sensor_readings_tuples = (await state.get()).get("distances")
        temperatures_per_sensor = []
        if sensor_readings_tuples:
            temperatures_per_sensor = [temp for _, temp in sensor_readings_tuples]

        # Logic for sweeping base rainbow colors across layers/faces
        if time.ticks_diff(frame_start_ms, last_color_sweep_time_ms) > COLOR_CHANGE_INTERVAL:
            if (current_layer_for_sweep == len(shape.layers) - 1 and
                current_face_in_layer_for_sweep == len(shape.layers[current_layer_for_sweep]) - 1):
                current_layer_for_sweep = 0
                current_face_in_layer_for_sweep = 0
                current_color_index = (current_color_index + 1) % len(RAINBOW_COLORS)
            elif current_face_in_layer_for_sweep == len(shape.layers[current_layer_for_sweep]) - 1:
                current_layer_for_sweep += 1
                current_face_in_layer_for_sweep = 0
            else:
                current_face_in_layer_for_sweep += 1
            last_color_sweep_time_ms = frame_start_ms

        # Determine base color for each face based on the sweep progression
        base_colors_for_each_face = {} # Map: actual_face_idx -> color_tuple
        for layer_idx, layer_content in enumerate(shape.layers):
            for face_idx_in_layer, actual_face_idx in enumerate(layer_content):
                if (layer_idx < current_layer_for_sweep or
                    (layer_idx == current_layer_for_sweep and face_idx_in_layer < current_face_in_layer_for_sweep)):
                    base_colors_for_each_face[actual_face_idx] = RAINBOW_COLORS[(current_color_index + 1) % len(RAINBOW_COLORS)]
                else:
                    base_colors_for_each_face[actual_face_idx] = RAINBOW_COLORS[current_color_index % len(RAINBOW_COLORS)]
        
        # Apply colors and brightness pulse to each face defined in layers
        for layer_idx, layer_content in enumerate(shape.layers):
            for face_idx_in_layer, actual_face_idx in enumerate(layer_content):
                if actual_face_idx >= shape.num_faces: # Safety check against out-of-bounds face index
                    continue

                base_color = base_colors_for_each_face.get(actual_face_idx, RAINBOW_COLORS[0])

                # Get temperature for this specific face by checking all its mapped sensors for the highest temp
                face_temp = 0 # Default to 0 if no sensor mapped or no data
                if actual_face_idx < len(shape.face_to_sensors) and shape.face_to_sensors[actual_face_idx]:
                    max_temp_for_this_face = 0
                    # Iterate over all sensors mapped to this face
                    for sensor_idx in shape.face_to_sensors[actual_face_idx]:
                        # Check if the sensor_idx is valid and its temperature data exists
                        if sensor_idx < len(temperatures_per_sensor) and temperatures_per_sensor[sensor_idx] is not None:
                            current_sensor_temp = temperatures_per_sensor[sensor_idx]
                            if current_sensor_temp > max_temp_for_this_face:
                                max_temp_for_this_face = current_sensor_temp
                    face_temp = max_temp_for_this_face
                
                current_brightness_factor = BASE_BRIGHTNESS # Default brightness (for temp < TEMP_MIN_PULSE)
                pulse_active = False
                frequency_hz = 0.0

                # Determine if face should pulse and calculate its frequency
                if face_temp >= TEMP_MIN_PULSE:
                    pulse_active = True
                    # Clamp temperature for frequency calculation to the sensor's max value
                    clamped_temp = min(face_temp, TEMP_MAX_SENSOR_VAL) 
                    
                    # Linearly interpolate frequency between FREQ_HZ_MIN and FREQ_HZ_MAX
                    if (TEMP_MAX_SENSOR_VAL - TEMP_MIN_PULSE) > 0:
                        ratio = (clamped_temp - TEMP_MIN_PULSE) / (TEMP_MAX_SENSOR_VAL - TEMP_MIN_PULSE)
                        frequency_hz = FREQ_HZ_MIN + (FREQ_HZ_MAX - FREQ_HZ_MIN) * ratio
                    else:
                        frequency_hz = FREQ_HZ_MIN
                
                if pulse_active:
                    face_phases[actual_face_idx] += 2 * math.pi * frequency_hz * dt_seconds
                    face_phases[actual_face_idx] %= (2 * math.pi)
                    current_brightness_factor = 0.75 + 0.25 * math.sin(face_phases[actual_face_idx])
                
                # Apply brightness to color based on the new rule
                value_to_add_to_zero_channels = (current_brightness_factor - BASE_BRIGHTNESS) * 50.0
                
                new_color_channels = []
                for c_val in base_color:
                    if c_val == 0:
                        # For a 0 channel, add the calculated pulsing value (ranges 0-25)
                        channel_val = value_to_add_to_zero_channels
                    else:
                        # For non-zero channels, scale by the overall brightness factor (0.5-1.0)
                        channel_val = c_val * current_brightness_factor
                    
                    # Ensure final channel value is an int and clamped to [0, 255]
                    new_color_channels.append(max(0, min(255, int(channel_val))))
                bright_color = tuple(new_color_channels)
                
                shape.set_face_color(actual_face_idx, bright_color)
        shape.write() # Write all LED changes to the strip
        
        # Frame delay to achieve target FRAME_TIME
        elapsed_frame_ms = time.ticks_diff(time.ticks_ms(), frame_start_ms)
        sleep_duration_ms = FRAME_TIME - elapsed_frame_ms
        if sleep_duration_ms > 0:
            await asyncio.sleep_ms(sleep_duration_ms)
            

