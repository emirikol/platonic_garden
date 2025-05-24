import asyncio
import math
import random
import time
from animations.utils import get_all_colors
from utils import SharedState
from shape import Shape

# Physics parameters (from parabola.py, potentially adjustable)
G = 8.0  # m/s² (acts in -z_orb direction, which is vertical)
INITIAL_VX_ORB = 1.0  # m/s
INITIAL_VZ_ORB_VERTICAL = 4.0  # m/s (vertical speed)
ORB_Y_DEPTH = 0.5 # m (fixed depth plane for the orb's 2D parabolic motion)
DT = 0.05  # s (time step for physics simulation)
FRAME_TIME_MS = int(DT * 1000)

# Orb's visual influence
ORB_MAX_EFFECT_DISTANCE = 1.5 # m (distance beyond which orb has no brightness effect)
ORB_BASE_COLOR_CYCLE_TIME_S = 10 # Time in seconds to cycle through orb base colors

# Sensor-driven pulse parameters
PULSE_FREQ_MIN_HZ = 0.5  # Hz (pulse frequency when sensor detects object at max_dist)
PULSE_FREQ_MAX_HZ = 3.0  # Hz (pulse frequency when sensor detects object at min_dist)
SENSOR_DIST_FOR_MAX_FREQ = 50   # mm (sensor units, e.g., object at 50mm for max freq)
SENSOR_DIST_FOR_MIN_FREQ = 200 # mm (sensor units, e.g., object at 200mm for min freq)
# Max raw sensor distance reading, used for clamping. (VL53L1X can report up to 4000mm in ideal conditions)
# For pulsing logic, we might only care about a smaller range, e.g. up to 255 if that's what "distances" provides.
# Let's assume distances are in mm and we care about the SENSOR_DIST_FOR_MIN_FREQ range.
MAX_SENSOR_DISTANCE_MM = 255

def interpolate_colors(color1, color2, factor):
    """Interpolate between two colors based on a factor (0 to 1)."""
    return (
        int(color1[0] + (color2[0] - color1[0]) * factor),
        int(color1[1] + (color2[1] - color1[1]) * factor),
        int(color1[2] + (color2[2] - color1[2]) * factor)
    )

def get_pulse_frequency(distance_mm):
    """Convert sensor distance to pulse frequency."""
    # Clamp distance to valid range
    distance_mm = max(SENSOR_DIST_FOR_MAX_FREQ, min(distance_mm, SENSOR_DIST_FOR_MIN_FREQ))
    
    # Normalize distance to 0-1 range (inverted so closer = higher value)
    dist_factor = 1.0 - ((distance_mm - SENSOR_DIST_FOR_MAX_FREQ) / 
                        (SENSOR_DIST_FOR_MIN_FREQ - SENSOR_DIST_FOR_MAX_FREQ))
    
    # Interpolate between min and max frequency
    return PULSE_FREQ_MIN_HZ + (PULSE_FREQ_MAX_HZ - PULSE_FREQ_MIN_HZ) * dist_factor

async def animate(
        shape: Shape,
        stop_event: asyncio.Event,
        state: SharedState
) -> None:
    all_colors = get_all_colors()
    if not all_colors:
        all_colors = [(100, 100, 100)] # Fallback color
    
    # Shuffle all_colors for variety each time animation starts (Fisher-Yates shuffle)
    n = len(all_colors)
    if n > 1: # No need to shuffle if 0 or 1 elements
        for i in range(n - 1, 0, -1):
            j = random.randint(0, i) # random.randint is inclusive for both ends
            all_colors[i], all_colors[j] = all_colors[j], all_colors[i]

    current_orb_color_index = 0
    # Determine initial pulse target color index
    # Ensure it's different if possible, otherwise it will be the same if only one color exists
    current_pulse_target_color_index = (current_orb_color_index + 1) % len(all_colors)
    
    orb_base_color = all_colors[current_orb_color_index]
    pulse_target_color = all_colors[current_pulse_target_color_index]
    
    last_orb_color_change_time_ms = time.ticks_ms()

    # Orb's state for 2D parabolic motion (x, z_vertical) and its velocities
    # (y_depth is fixed at ORB_Y_DEPTH)
    # Parabola.py's (x, z, y) maps to our (orb_x, orb_z_vertical, ORB_Y_DEPTH)
    # Parabola.py's face_pos[0] is x, face_pos[1] is z(vertical), face_pos[2] is y(depth)
    # Assuming our face_positions are [std_x, std_y_depth, std_z_vertical] for consistency
    # or more standardly [std_x, std_y_vertical, std_z_depth]
    # Let's assume standard face_positions: [face_x, face_y_vertical, face_z_depth]
    # Then orb state is (orb_x, orb_y_vertical, orb_z_depth_fixed) for physics,
    # and compared against (face_x, face_y_vertical, face_z_depth)
    # Let's use parabola.py's convention for particle state (x, z_vert) and fixed y_depth.
    # Particle state: (p_x, p_z_vert) and fixed p_y_depth = ORB_Y_DEPTH.
    # Face state: face_positions[i] = (f_x, f_y_vert, f_z_depth)
    # Distance needs to be: (p_x - f_x)^2 + (p_y_depth - f_y_depth_coord_of_face)^2 + (p_z_vert - f_z_vert_coord_of_face)^2
    # From parabola.py: dist_sq = (p_x - f_pos[0])**2 + (p_z_vert - f_pos[1])**2 + (p_y_depth - f_pos[2])**2
    # This means f_pos[0] = x, f_pos[1] = z_vertical_equivalent, f_pos[2] = y_depth_equivalent
    # So, if face_positions are standard [std_x, std_y_vert, std_z_depth], then:
    # f_pos[0] is std_x
    # f_pos[1] is std_y_vert
    # f_pos[2] is std_z_depth
    # This is consistent.

    orb_x, orb_z_vertical = 0.0, 0.01
    orb_vx, orb_vz_vertical = INITIAL_VX_ORB, INITIAL_VZ_ORB_VERTICAL
    
    # Sensor pulse phases (one per face)
    face_pulse_phases = [0.0] * shape.num_faces
    face_pulse_freqs = [PULSE_FREQ_MIN_HZ] * shape.num_faces
    
    # Animation loop
    last_frame_time = time.ticks_ms()
    
    while not stop_event.is_set():
        frame_start = time.ticks_ms()
        
        # Get sensor data
        sensor_data = (await state.get()).get("distances", [])
        
        # Update orb physics
        dt = time.ticks_diff(frame_start, last_frame_time) / 1000.0  # Convert to seconds
        last_frame_time = frame_start
        
        # Update orb position and velocity
        orb_x += orb_vx * dt
        orb_z_vertical += orb_vz_vertical * dt
        orb_vz_vertical -= G * dt  # Apply gravity
        
        # Check boundaries and bounce/reset
        if orb_x <= 0:
            orb_x = 0.0
            orb_vx = INITIAL_VX_ORB
        elif orb_x >= 1:
            orb_x = 1.0
            orb_vx = -INITIAL_VX_ORB
            
        if orb_z_vertical <= 0:
            orb_z_vertical = 0.0
            orb_vz_vertical = INITIAL_VZ_ORB_VERTICAL
            
        # Check for orb color change
        current_time_ms = time.ticks_ms()
        if time.ticks_diff(current_time_ms, last_orb_color_change_time_ms) >= ORB_BASE_COLOR_CYCLE_TIME_S * 1000:
            # Update color indices
            current_orb_color_index = (current_orb_color_index + 1) % len(all_colors)
            current_pulse_target_color_index = (current_pulse_target_color_index + 1) % len(all_colors)
            
            # Update colors
            orb_base_color = all_colors[current_orb_color_index]
            pulse_target_color = all_colors[current_pulse_target_color_index]
            
            last_orb_color_change_time_ms = current_time_ms
        
        # Update each face
        for face_idx in range(shape.num_faces):
            face_pos = shape.face_positions[face_idx]
            
            # Calculate distance from orb to face
            dist_sq = ((orb_x - face_pos[0])**2 + 
                      (orb_z_vertical - face_pos[1])**2 + 
                      (ORB_Y_DEPTH - face_pos[2])**2)
            dist = math.sqrt(dist_sq)
            
            # Normalize distance for color interpolation
            dist_factor = min(1.0, dist / ORB_MAX_EFFECT_DISTANCE)
            
            # Get sensor data for this face
            max_sensor_temp = 0
            min_sensor_dist = MAX_SENSOR_DISTANCE_MM
            if face_idx < len(shape.face_to_sensors):
                for sensor_idx in shape.face_to_sensors[face_idx]:
                    if (sensor_idx < len(sensor_data) and 
                        sensor_data[sensor_idx] is not None):
                        # Get temperature and distance from sensor data tuple
                        sensor_dist, sensor_temp = sensor_data[sensor_idx]
                        if sensor_temp is not None:
                            max_sensor_temp = max(max_sensor_temp, sensor_temp)
                        if sensor_dist is not None:
                            min_sensor_dist = min(min_sensor_dist, sensor_dist)
            
            # Update pulse frequency based on closest sensor distance
            face_pulse_freqs[face_idx] = get_pulse_frequency(min_sensor_dist)
            
            # Update pulse phase
            face_pulse_phases[face_idx] += face_pulse_freqs[face_idx] * 2 * math.pi * dt
            
            # Calculate pulse factor (0 to 1)
            pulse_factor = 0.5 + 0.5 * math.sin(face_pulse_phases[face_idx])
            
            # Combine orb influence with sensor temperature
            # First interpolate between orb colors based on distance
            orb_color = interpolate_colors(orb_base_color, pulse_target_color, dist_factor)
            
            # Then factor in sensor temperature
            temp_factor = max_sensor_temp / 255.0  # Normalize to 0-1
            final_color = interpolate_colors(orb_color, pulse_target_color, temp_factor * pulse_factor)
            
            # Set the face color
            shape.set_face_color(face_idx, final_color)
        
        # Update LEDs
        shape.write()
        
        # Frame timing
        frame_duration = time.ticks_diff(time.ticks_ms(), frame_start)
        if frame_duration < FRAME_TIME_MS:
            await asyncio.sleep_ms(FRAME_TIME_MS - frame_duration) 