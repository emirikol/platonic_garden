import asyncio
import time
import neopixel
from utils import SharedState
from animations.utils import get_all_colors, set_face_color

FRAME_TIME_MS = int(1000/20)
BASE_CHANGE_COLOR_TIME_MS = int(1000/3)

# Maximum possible temperature value from a sensor (used for normalization)
MAX_SENSOR_TEMP_VALUE = 255.0 


def interpolate_color(color1: tuple[int, int, int], color2: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    """Linearly interpolates between two colors."""
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    r = int(r1 + (r2 - r1) * factor)
    g = int(g1 + (g2 - g1) * factor)
    b = int(b1 + (b2 - b1) * factor)
    return (r, g, b)


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
    
    colors = get_all_colors()
    # print(colors) # Commented out or removed print
    num_colors = len(colors)
    
    source_color_index = 0
    target_color_index = 1
    
    transition_start_time = time.ticks_ms()

    while not stop_event.is_set():
        frame_start_time = time.ticks_ms()

        # Get sensor data (list of (distance, temperature) tuples)
        sensor_data = (await state.get()).get("distances")
        
        # Calculate effective change color time
        # Start with the base time (animation speed if all sensors are at 0 temp or no sensors active)
        effective_change_color_time_ms = float(BASE_CHANGE_COLOR_TIME_MS)
        
        if sensor_data and MAX_SENSOR_TEMP_VALUE > 0: # Ensure MAX_SENSOR_TEMP_VALUE is not zero
            for distance_val, temp_val in sensor_data:
                # Only consider sensors that are actively providing distance readings and have a temperature value
                if distance_val is not None and temp_val is not None:
                    # Ensure temp_val is not negative and not above max, then normalize
                    clamped_temp = max(0.0, min(float(temp_val), MAX_SENSOR_TEMP_VALUE))
                    normalized_temp_contribution = clamped_temp / MAX_SENSOR_TEMP_VALUE
                    effective_change_color_time_ms += normalized_temp_contribution * BASE_CHANGE_COLOR_TIME_MS
        
        # Ensure the final time is an integer for time functions
        effective_change_color_time_ms = int(effective_change_color_time_ms)

        # Calculate transition progress
        elapsed_since_transition_start = time.ticks_diff(frame_start_time, transition_start_time)
        
        current_transition_duration = effective_change_color_time_ms
        if current_transition_duration <= 0: # Prevent division by zero or negative time
            current_transition_duration = BASE_CHANGE_COLOR_TIME_MS # Default to base if calculation is problematic

        transition_progress = min(elapsed_since_transition_start / current_transition_duration, 1.0)

        if transition_progress >= 1.0:
            source_color_index = target_color_index
            target_color_index = (target_color_index + 1) % num_colors
            transition_start_time = frame_start_time
            transition_progress = 0.0 

        face_number = 0
        for i, layer in enumerate(layers):
            for j, face_index in enumerate(layer):
                # Determine the "effective" source and target colors for this specific face's swirl
                # This maintains the swirling pattern while fading
                current_face_source_color = colors[(source_color_index + face_number) % num_colors]
                current_face_target_color = colors[(target_color_index + face_number) % num_colors]
                
                interpolated_color = interpolate_color(current_face_source_color, current_face_target_color, transition_progress)
                set_face_color(np, leds_per_face, face_index, interpolated_color)
                face_number += 1
        np.write()
        await asyncio.sleep_ms(FRAME_TIME_MS - time.ticks_diff(time.ticks_ms(), frame_start_time))
