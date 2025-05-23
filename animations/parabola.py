import asyncio
import math
import random
import time
from utils import SharedState
from shape import Shape
import neopixel


# physics parameters (unchanged)
G               = 8.0          # m/s² (acts in −y)
INITIAL_VX      = 1.0          # m/s
INITIAL_VZ      = 4.0          # m/s
DT              = 0.05         # 1/20 s
FRAME_TIME_MS   = int(DT * 1000)

def step(x, z, y, vx, vz):
    """Advance the ball by one time slice (dt) and apply the
    ground/reset rules you specified."""

    # 1. Integrate motion for dt
    x += vx * DT
    z += vz * DT - 0.5 * G * DT * DT
    vz -= G * DT

    # 2. Check for contact with the ground (y ≤ 0)
    if z <= 0.0:
        if x <= 0.0:        # left side or overshoot
            x, z, y = 0.0, 0.0, 0.0
            vx, vz  =  INITIAL_VX, INITIAL_VZ
        elif x >= 1.0:      # right side or overshoot
            x, z, y = 1.0, 0.0, 0.0
            vx, vz  = -INITIAL_VX, INITIAL_VZ
        else:
            # if it somehow lands between 0 < x < 1 just stick it
            # where it touched down and kill vertical speed
            z  = 0.0
            vz = 0.0
    return x, z, y, vx, vz


async def animate(
        np: neopixel.NeoPixel,
        shape: Shape,
        stop_event: asyncio.Event,
        state: SharedState
    ) -> None:
    color_channels = list(range(3))
    max_color_channel = color_channels.pop(random.randint(0, len(color_channels) - 1))
    ball_channel = color_channels.pop(random.randint(0, len(color_channels) - 1))
    sensor_channel = color_channels[0]

    x, z, y = 0.0, 0.0, 0.5
    vx, vz  = INITIAL_VX, INITIAL_VZ

    while not stop_event.is_set():
        frame_start = time.time_ns()
        distances = (await state.get()).get('distances')
        x, z, y, vx, vz = step(x, z, y, vx, vz)
        for face_id, face_pos in enumerate(shape.face_positions):
            distance = min(1.0, math.sqrt((x - face_pos[0])**2 + (z - face_pos[1])**2 + (y - face_pos[2])**2))
            color = [0, 0, 0]
            color[max_color_channel] = 255
            color[ball_channel] = int(255 * (1 - distance))
            if len(shape.face_to_sensors[face_id]) == 0:
                sensor_color = 0
            else:
                sensor_color = max([distances[sensor][1] for sensor in shape.face_to_sensors[face_id]])
            color[sensor_channel] = sensor_color
            shape.set_face_color(np, face_id, tuple(color))
        np.write()
        await asyncio.sleep_ms(int(FRAME_TIME_MS - (time.time_ns() - frame_start)/1000000))

