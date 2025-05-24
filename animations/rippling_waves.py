import asyncio
import time
import math
import random
from animations.utils import get_all_colors
from utils import SharedState
from read_sensor import TempratureSettings
from shape import Shape

# Animation timing constants
FRAME_TIME_MS = int(1000/20)  # 20 FPS
COLOR_TRANSITION_TIME_MS = 2000  # Time to transition between base colors

# Ripple effect constants
RIPPLE_DECAY_RATE = 0.95  # Slower decay for more visible propagation
RIPPLE_PROPAGATION_RATE = 0.7  # Reduced to prevent infinite circulation
MAX_RIPPLE_INTENSITY = 1.0  # Full intensity
MIN_TEMP_THRESHOLD = 40  # Temperature threshold on 0-255 scale
MAX_TEMP = 255  # Maximum temperature value (full sensor range)
TEMP_SENSITIVITY = 0.3  # How much of the range above threshold triggers full intensity
BASE_COLOR_DIMMING = 0.6  # Much dimmer base state for contrast
RIPPLE_PULSE_FREQ = 3.0  # Faster pulses
DEBUG_PRINT_INTERVAL_MS = 500  # Only print debug every 500ms to avoid spam

class RippleState:
    def __init__(self, num_faces: int):
        self.intensities = [0.0] * num_faces  # Ripple intensity per face
        self.target_intensities = [0.0] * num_faces  # Target intensity for smooth transitions
        self.phase = 0.0  # Phase for pulsing effect
        self.propagation_phase = 0.0  # Separate phase for propagation effect
        self.active_sensors = [False] * num_faces  # Tracks which faces have active sensors
        self.propagation_levels = [0] * num_faces  # Tracks how many steps away from sensor
        self.last_debug_print = 0  # Track last debug print time
        self.prev_sensor_temps = [0.0] * num_faces  # Previous temperature readings
        self.propagation_sources = [set() for _ in range(num_faces)]  # Track propagation sources

def get_adjacent_faces_in_layer(face_index: int, layers: tuple[tuple[int, ...], ...]) -> list[int]:
    """Find adjacent faces in the same layer as the given face."""
    for layer in layers:
        if face_index in layer:
            layer_list = list(layer)
            face_pos = layer_list.index(face_index)
            adjacent = []
            
            # Check left neighbor (wrap around)
            left_pos = (face_pos - 1) % len(layer)
            adjacent.append(layer_list[left_pos])
            
            # Check right neighbor (wrap around)
            right_pos = (face_pos + 1) % len(layer)
            adjacent.append(layer_list[right_pos])
            
            return adjacent
    return []

def interpolate_colors(color1: tuple[int, int, int], color2: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    """Smoothly interpolate between two colors."""
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    r = int(r1 + (r2 - r1) * factor)
    g = int(g1 + (g2 - g1) * factor)
    b = int(b1 + (b2 - b1) * factor)
    return (r, g, b)

def apply_ripple_to_color(
    base_color: tuple[int, int, int],
    ripple_intensity: float,
    sensor_phase: float,
    propagation_phase: float,
    has_active_sensor: bool,
    propagation_level: int
) -> tuple[int, int, int]:
    """Modify color based on ripple intensity with out-of-phase propagation."""
    # Base color is already dimmed for contrast with ripples
    r, g, b = base_color
    
    # Calculate pulsing factor based on phase
    if has_active_sensor:
        # Active sensors pulse more dramatically
        pulse = 0.5 + 0.5 * math.sin(sensor_phase)
    else:
        # Propagation pulses are more subtle
        pulse = 0.7 + 0.3 * math.sin(propagation_phase + propagation_level * math.pi / 2)
    
    # Combine ripple intensity with pulse
    intensity = ripple_intensity * pulse
    
    # Scale up the color based on intensity
    r = int(min(255, r + (255 - r) * intensity))
    g = int(min(255, g + (255 - g) * intensity))
    b = int(min(255, b + (255 - b) * intensity))
    
    return (r, g, b)

async def animate(
        shape: Shape,
        stop_event: asyncio.Event,
        state: SharedState
    ) -> None:
    # Initialize ripple state
    ripple = RippleState(shape.num_faces)
    
    # Get all available colors and randomly select two
    all_colors = get_all_colors()
    if not all_colors:
        all_colors = [(255, 0, 255)]  # Fallback to purple if no colors available
    
    # Shuffle colors for variety
    n = len(all_colors)
    for i in range(n - 1, 0, -1):
        j = random.randint(0, i)
        all_colors[i], all_colors[j] = all_colors[j], all_colors[i]
    
    # Take first color as base
    base_color = tuple(int(c * BASE_COLOR_DIMMING) for c in all_colors[0])
    print(f"\nSelected base color: {base_color}")
    
    # Animation timing variables
    last_frame_time = time.ticks_ms()
    frame_count = 0
    
    while not stop_event.is_set():
        frame_start = time.ticks_ms()
        frame_count += 1
        
        # Get sensor data
        sensor_data = (await state.get()).get("distances", [])
        
        # Update phases
        dt = time.ticks_diff(frame_start, last_frame_time) / 1000.0  # Convert to seconds
        ripple.phase += RIPPLE_PULSE_FREQ * 2 * math.pi * dt
        ripple.propagation_phase += (RIPPLE_PULSE_FREQ * 0.7) * 2 * math.pi * dt
        last_frame_time = frame_start
        
        # Collect info about active faces for debug printing
        for face_idx in range(shape.num_faces):
            # Decay current ripple intensity
            ripple.intensities[face_idx] *= RIPPLE_DECAY_RATE
            
            # Check sensors for this face
            if face_idx < len(shape.face_to_sensors):
                max_temp = 0
                active_sensors = []
                for sensor_idx in shape.face_to_sensors[face_idx]:
                    if sensor_idx < len(sensor_data) and sensor_data[sensor_idx] is not None:
                        temp = sensor_data[sensor_idx][1]  # Get temperature value
                        if temp is not None and temp > max_temp:
                            max_temp = temp
                            active_sensors.append((sensor_idx, temp))
                
                # Update ripple intensity based on temperature
                if max_temp > MIN_TEMP_THRESHOLD:
                    # Calculate how far above threshold we are (0 to 1 range)
                    temp_factor = min(1.0, (max_temp - MIN_TEMP_THRESHOLD) / (MAX_TEMP * TEMP_SENSITIVITY))
                    ripple.intensities[face_idx] = max(ripple.intensities[face_idx], temp_factor * MAX_RIPPLE_INTENSITY)
                    ripple.active_sensors[face_idx] = True
                    ripple.propagation_levels[face_idx] = 0
                    
                    # This face becomes a propagation source
                    for other_face in range(shape.num_faces):
                        if other_face != face_idx:
                            ripple.propagation_sources[other_face].add(face_idx)
                else:
                    ripple.active_sensors[face_idx] = False
            
            # Apply color with ripple effect
            final_color = apply_ripple_to_color(
                base_color,
                ripple.intensities[face_idx],
                ripple.phase,
                ripple.propagation_phase,
                ripple.active_sensors[face_idx],
                ripple.propagation_levels[face_idx]
            )
            shape.set_face_color(face_idx, final_color)
        
        # Write all LED updates
        shape.write()
        
        # Calculate remaining frame time and sleep
        frame_duration = time.ticks_diff(time.ticks_ms(), frame_start)
        if frame_duration < FRAME_TIME_MS:
            await asyncio.sleep_ms(FRAME_TIME_MS - frame_duration) 