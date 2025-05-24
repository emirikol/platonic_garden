import asyncio
import time
from utils import SharedState
from animations.utils import get_all_colors
from shape import Shape

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
        shape: Shape,
        stop_event: asyncio.Event,
        state: SharedState
    ) -> None:
    """
    Creates a swirling color effect that responds to sensor data.
    The animation cycles through available colors, creating smooth transitions
    between them. Sensor data influences the brightness and color mixing.
    """
    # Get available colors
    colors = get_all_colors()
    if not colors:
        colors = [(255, 0, 0)]  # Fallback to red if no colors available
    
    # Animation state
    current_color_idx = 0
    next_color_idx = (current_color_idx + 1) % len(colors)
    last_color_change = time.ticks_ms()
    
    # Main animation loop
    while not stop_event.is_set():
        frame_start = time.ticks_ms()
        
        # Get sensor data
        sensor_data = (await state.get()).get('distances', [])
        
        # Check if it's time to change colors
        current_time = time.ticks_ms()
        time_since_last_change = time.ticks_diff(current_time, last_color_change)
        
        if time_since_last_change >= BASE_CHANGE_COLOR_TIME_MS:
            # Update color indices
            current_color_idx = next_color_idx
            next_color_idx = (next_color_idx + 1) % len(colors)
            last_color_change = current_time
            time_since_last_change = 0
        
        # Calculate color transition progress (0.0 to 1.0)
        transition_progress = time_since_last_change / BASE_CHANGE_COLOR_TIME_MS
        
        # Get current and next colors
        current_color = colors[current_color_idx]
        next_color = colors[next_color_idx]
        
        # Interpolate between current and next color
        base_color = interpolate_color(current_color, next_color, transition_progress)
        
        # Update each face's color based on sensor data
        for face_idx in range(shape.num_faces):
            # Get maximum temperature from sensors for this face
            max_temp = 0
            if face_idx < len(shape.face_to_sensors):
                for sensor_idx in shape.face_to_sensors[face_idx]:
                    if (sensor_idx < len(sensor_data) and 
                        sensor_data[sensor_idx] is not None and 
                        sensor_data[sensor_idx][1] is not None):
                        max_temp = max(max_temp, sensor_data[sensor_idx][1])
            
            # Normalize temperature (0.0 to 1.0)
            temp_factor = max_temp / MAX_SENSOR_TEMP_VALUE
            
            # Modify color based on temperature
            # Higher temperatures make the color brighter
            modified_color = tuple(min(255, int(c * (1.0 + temp_factor))) for c in base_color)
            
            # Set the face color
            shape.set_face_color(face_idx, modified_color)
        
        # Update LEDs
        shape.write()
        
        # Frame timing
        frame_duration = time.ticks_diff(time.ticks_ms(), frame_start)
        if frame_duration < FRAME_TIME_MS:
            await asyncio.sleep_ms(FRAME_TIME_MS - frame_duration)
