import asyncio
import time
from animations.utils import set_face_color
from utils import SharedState

RAINBOW_COLORS = [
    (255, 0, 0),
    (255, 165, 0),
    (255, 255, 0),
    (0, 255, 0),
    (0, 0, 255),
    (75, 0, 130),
    (148, 0, 211),
]


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
    current_color_index = 0
    while True:
        for i in range(len(layers)):
            for face in layers[i]:
                set_face_color(np, leds_per_face, face, RAINBOW_COLORS[(current_color_index+i)%len(RAINBOW_COLORS)])
        np.write()
        current_color_index = (current_color_index + 1) % len(RAINBOW_COLORS)
        await asyncio.sleep_ms(1000)
        if stop_event.is_set():
            return

