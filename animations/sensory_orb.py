import asyncio
import math
import random
import time
from animations.utils import set_face_color, get_all_colors
from utils import SharedState

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
MAX_SENSOR_DISTANCE_MM = 255 # Assuming sensor readings are capped or relevant up to this.


def step_orb_motion(x_orb, z_orb_vertical, vx_orb, vz_orb_vertical):
    """
    Advance the orb's position and velocity by one time slice (DT).
    Handles bounces and resets based on predefined boundaries.
    Matches parabola.py's physics logic, with z_orb_vertical being the vertical axis.
    """
    # 1. Integrate motion for DT
    x_orb += vx_orb * DT
    z_orb_vertical += vz_orb_vertical * DT - 0.5 * G * DT * DT
    vz_orb_vertical -= G * DT

    # 2. Check for contact with the "ground" (z_orb_vertical <= 0) and boundaries (x_orb)
    if z_orb_vertical <= 0.0:
        if x_orb <= 0.0:  # Hit ground on left side or overshoot
            x_orb, z_orb_vertical = 0.0, 0.0
            vx_orb, vz_orb_vertical = INITIAL_VX_ORB, INITIAL_VZ_ORB_VERTICAL
        elif x_orb >= 1.0:  # Hit ground on right side or overshoot
            x_orb, z_orb_vertical = 1.0, 0.0
            vx_orb, vz_orb_vertical = -INITIAL_VX_ORB, INITIAL_VZ_ORB_VERTICAL
        else: # Landed on the ground within x boundaries
            z_orb_vertical = 0.0
            vz_orb_vertical = 0.0 # Stop vertical motion, could also add some bounce damping
    
    # Optional: Add horizontal boundaries if needed, e.g., if x_orb goes < 0 or > 1 while in air.
    # For now, matching parabola.py which only resets on ground contact with boundary conditions.

    return x_orb, z_orb_vertical, vx_orb, vz_orb_vertical


async def animate(
        np: 'neopixel.NeoPixel',
        leds_per_face: int,
        num_faces: int,
        layers: tuple[tuple[int, ...], ...],
        sensors_to_face: list[list[int]],
        face_to_sensors: list[list[int]],
        face_positions: list[list[float]], # Expected: [x, y_horizontal, z_vertical] or [std_x, std_y, std_z]
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

    orb_x, orb_z_vertical = 0.0, 0.01 # Start slightly above ground
    vx_orb, vz_orb_vertical = INITIAL_VX_ORB, INITIAL_VZ_ORB_VERTICAL
    
    face_phases = [random.uniform(0, 2 * math.pi) for _ in range(num_faces)] # Random initial phases

    np.fill((0,0,0))
    np.write()

    while not stop_event.is_set():
        frame_start_ns = time.time_ns()
        current_time_ms = time.ticks_ms() # Current time for logic
        dt_seconds = FRAME_TIME_MS / 1000.0

        # Update orb base color periodically
        # ORB_BASE_COLOR_CYCLE_TIME_S is in seconds, convert to ms
        if time.ticks_diff(current_time_ms, last_orb_color_change_time_ms) > (ORB_BASE_COLOR_CYCLE_TIME_S * 1000):
            current_orb_color_index = (current_orb_color_index + 1) % len(all_colors)
            # Update pulse target color to be the next one, ensuring it cycles
            current_pulse_target_color_index = (current_orb_color_index + 1) % len(all_colors)
            
            orb_base_color = all_colors[current_orb_color_index]
            pulse_target_color = all_colors[current_pulse_target_color_index]
            last_orb_color_change_time_ms = current_time_ms
        # No else needed, orb_base_color and pulse_target_color persist from previous state or initialization

        # Get sensor data
        shared_data = await state.get()
        sensor_readings_tuples = shared_data.get("distances", []) # List of (distance_mm, temperature)

        # Update orb position
        orb_x, orb_z_vertical, vx_orb, vz_orb_vertical = step_orb_motion(
            orb_x, orb_z_vertical, vx_orb, vz_orb_vertical
        )

        for face_id in range(num_faces):
            face_pos = face_positions[face_id] # Expected: [x, y_vertical, z_depth]

            # 1. Calculate effect of orb proximity on brightness
            dist_sq_to_orb = (
                (orb_x - face_pos[0])**2 +             # delta_x^2
                (orb_z_vertical - face_pos[1])**2 +    # delta_y_vertical^2 (orb_z_vert vs face_y_vert)
                (ORB_Y_DEPTH - face_pos[2])**2         # delta_z_depth^2 (fixed orb_y_depth vs face_z_depth)
            )
            dist_to_orb = math.sqrt(dist_sq_to_orb)
            
            # Orb brightness factor (1.0 at dist=0, 0.0 at ORB_MAX_EFFECT_DISTANCE)
            orb_proximity_brightness_factor = max(0.0, 1.0 - (dist_to_orb / ORB_MAX_EFFECT_DISTANCE))

            # 2. Calculate sensor-driven pulse modulation
            min_sensor_dist_mm = float('inf')
            sensor_pulse_active = False
            
            if face_id < len(face_to_sensors) and face_to_sensors[face_id]:
                for sensor_idx in face_to_sensors[face_id]:
                    if sensor_idx < len(sensor_readings_tuples) and sensor_readings_tuples[sensor_idx] is not None:
                        # Assuming sensor_readings_tuples[sensor_idx] is (distance, temp)
                        # and distance is not excessively large (e.g. > MAX_SENSOR_DISTANCE_MM for "no object")
                        # Distance from sensor is typically in mm.
                        current_sensor_reading = sensor_readings_tuples[sensor_idx]
                        current_sensor_dist = current_sensor_reading[0] # This could be None

                        # Ensure current_sensor_dist is a number before comparison
                        if current_sensor_dist is not None and current_sensor_dist < SENSOR_DIST_FOR_MIN_FREQ : # Only consider "close" objects for pulsing
                             min_sensor_dist_mm = min(min_sensor_dist_mm, current_sensor_dist)
                             sensor_pulse_active = True # Activate pulse if any mapped sensor detects something close enough
            
            interpolation_factor_for_pulse = 0.0 # Default: shows orb_base_color

            if sensor_pulse_active and min_sensor_dist_mm <= SENSOR_DIST_FOR_MIN_FREQ : # Check again in case min_sensor_dist_mm wasn't updated
                # Clamp distance for frequency calculation
                clamped_dist = max(SENSOR_DIST_FOR_MAX_FREQ, min(min_sensor_dist_mm, SENSOR_DIST_FOR_MIN_FREQ))
                
                frequency_hz = PULSE_FREQ_MIN_HZ # Default to min frequency
                # Ratio: 1.0 for SENSOR_DIST_FOR_MAX_FREQ, 0.0 for SENSOR_DIST_FOR_MIN_FREQ
                # Avoid division by zero if min and max dists are the same
                denom = SENSOR_DIST_FOR_MIN_FREQ - SENSOR_DIST_FOR_MAX_FREQ
                if denom > 0:
                    ratio = (SENSOR_DIST_FOR_MIN_FREQ - clamped_dist) / denom
                    frequency_hz = PULSE_FREQ_MIN_HZ + (PULSE_FREQ_MAX_HZ - PULSE_FREQ_MIN_HZ) * ratio
                elif min_sensor_dist_mm <= SENSOR_DIST_FOR_MAX_FREQ: # If denom is 0 or less, and we are at/below max_freq distance
                    frequency_hz = PULSE_FREQ_MAX_HZ
                
                # Update phase for this face
                face_phases[face_id] += 2 * math.pi * frequency_hz * dt_seconds
                face_phases[face_id] %= (2 * math.pi)
                
                # Interpolation factor: varies between 0.0 (orb_base_color) and 1.0 (pulse_target_color)
                interpolation_factor_for_pulse = 0.5 + 0.5 * math.sin(face_phases[face_id])
            # else: interpolation_factor_for_pulse remains 0.0, so orb_base_color is used before brightness scaling

            # Combine effects: Orb proximity scales the base color, then pulse modulates it
            # Final brightness is product of orb proximity and pulse modulation
            # Allow pulse to make face bright even if orb is far, or make it dimmer.
            # Let's make the pulse modulate the orb's light.
            # If orb_proximity_brightness_factor is 0, then face is dark.
            # If orb_proximity_brightness_factor is >0, then pulse applies.
            # pulse_modulation_factor range [0.5, 1.0] -> this works as a scaler.
            
            # Interpolate between orb_base_color and pulse_target_color based on sensor pulse
            base_r, base_g, base_b = orb_base_color
            pulse_r, pulse_g, pulse_b = pulse_target_color

            interp_r = base_r * (1.0 - interpolation_factor_for_pulse) + pulse_r * interpolation_factor_for_pulse
            interp_g = base_g * (1.0 - interpolation_factor_for_pulse) + pulse_g * interpolation_factor_for_pulse
            interp_b = base_b * (1.0 - interpolation_factor_for_pulse) + pulse_b * interpolation_factor_for_pulse

            # Apply orb proximity brightness factor to the interpolated color
            final_brightness = orb_proximity_brightness_factor # Proximity factor directly scales the result

            # Apply to base color
            final_color_r = int(interp_r * final_brightness)
            final_color_g = int(interp_g * final_brightness)
            final_color_b = int(interp_b * final_brightness)
            
            # Clamp color values
            final_color = (
                max(0, min(255, final_color_r)),
                max(0, min(255, final_color_g)),
                max(0, min(255, final_color_b))
            )
            
            set_face_color(np, leds_per_face, face_id, final_color)

        np.write()

        # Frame delay
        frame_duration_ns = time.time_ns() - frame_start_ns
        sleep_ms = FRAME_TIME_MS - (frame_duration_ns // 1_000_000)
        if sleep_ms > 0:
            await asyncio.sleep_ms(sleep_ms) 