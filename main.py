import machine, neopixel
import time
import json
import asyncio
from typing import TypeVar, Generic, Callable, Optional, Dict, Any, TYPE_CHECKING
from copy import deepcopy
import sys

if TYPE_CHECKING:
    from types import ModuleType

from pathlib import Path
from utils import SharedState
from wifi_client import connect_to_wifi, fetch_animation_data, is_wifi_connected
from animations import ANIMATIONS
from read_sensor import read_sensor, TempratureSettings


def get_layers(shape_faces: list[dict]) -> tuple[tuple[int, ...], ...]:
    if not shape_faces:
        return tuple()
    max_layer = max(face['layer'] for face in shape_faces)
    layers = [[] for _ in range(max_layer + 1)]
    for face in shape_faces:
        layers[face['layer']].append((face['face_id'], face['index']))
    
    processed_layers = []
    for layer_list in layers:
        layer_list.sort(key=lambda x: x[1])
        processed_layers.append(tuple(item[0] for item in layer_list))
    return tuple(processed_layers)


def get_shape(file_path: Path) -> tuple[int, int, tuple[tuple[int, ...], ...]]:
    data = json.loads(file_path.read_text())
    
    leds_per_face = data.get('led_per_face')
    faces_data = data.get('faces')
    sensors = data.get('sensors')
    sensors_to_face = [[face for face in range(len(faces_data)) if i in faces_data[face]['sensors']] for i in range(sensors)]
    face_to_sensors = [face['sensors'] for face in faces_data]
    face_positions = [face['pos'] for face in faces_data]

    if leds_per_face is None or faces_data is None:
        raise ValueError(f"Invalid shape data in {file_path}")

    num_faces = len(faces_data)
    layers_map = get_layers(faces_data)
    return leds_per_face, num_faces, layers_map, sensors_to_face, face_to_sensors, face_positions


def set_face_color(np, leds_per_face, face_index, color):
    face_offset = leds_per_face * face_index
    for i in range(leds_per_face):
        np[face_offset + i] = color


def get_animations() -> dict[str, 'ModuleType']:
    return {name: getattr(__import__(f'animations.{name}'), name) for name in ANIMATIONS}


async def run_animations(
        np: neopixel.NeoPixel,
        leds_per_face: int,
        num_faces: int,
        layers: tuple[tuple[int, ...], ...],
        sensors_to_face: list[list[int]],
        face_to_sensors: list[list[int]],
        face_positions: list[list[float]],
        state: SharedState
    ) -> None:
    temp_settings = TempratureSettings()

    animations = get_animations()
    async def start_animation(animation_name: str) -> None:
        stop_event = asyncio.Event()
        temp_settings.set_values_to_default()
        task = asyncio.create_task(animations[animation_name].animate(
            np, leds_per_face, num_faces, layers, sensors_to_face, face_to_sensors, face_positions, stop_event, state
            ))
        return task, stop_event
    
    if Path('force_animation.txt').exists():
        force_animation = Path('force_animation.txt').read_text().strip()
        print(f"Forcing animation: {force_animation}")
        task, stop_event = await start_animation(force_animation)
        await asyncio.gather(task)

    current_animation = list(animations.keys())[0]
    task, stop_event = await start_animation(current_animation)
    while True:
        try:
            new_animation = (await state.get()).get('animation')
            if new_animation is not None:
                if new_animation != current_animation:
                    current_animation = new_animation
                    if task is not None:
                        stop_event.set()
                        await asyncio.gather(task)
                    task, stop_event = await start_animation(new_animation)
            await asyncio.sleep(0.05)
        except Exception as e:
            sys.print_exception(e)
            error_animation(np)


async def restart_in_30_minutes() -> None:
    await asyncio.sleep(30 * 60)
    print("Restarting after 30 minutes, see you soon!")
    machine.reset()


async def get_animation_name(state: SharedState):
    while True:
        animation_name = await fetch_animation_data()
        if animation_name is None:
            if not await is_wifi_connected():
                await connect_to_wifi()
        else:
            #await state.update('animation', "flashing_purple")
            await state.update('animation', animation_name)
            await asyncio.sleep(1)


def error_animation(np: neopixel.NeoPixel) -> None:
    try:
        for i in range(3):
            np.fill((255, 0, 0))
            np.write()
            time.sleep(0.5)
            np.fill((0, 0, 0))
            np.write()
            time.sleep(0.5)
    except Exception as e:
        sys.print_exception(e)


def init_animation(np: neopixel.NeoPixel) -> None:
    print("""
       ^     +------+.           /\              _----------_,                 _-_. 
      /|\    |`.    | `.       .'  `.          ,"__         _-:,            _-',^. `-_.
     / | \   |  `+--+---+    .'      `.       /    ""--_--""...:\       ._-' ,'   `.   `-_
    /  |  \  |   |  |   |   <          >     /         |.........\     !`-_._________`-':::
    '-.|.-'  +---+--+.  |    `.      .'     /          |..........\    !   /\        /\::::
              `. |    `.|      `.  .'      /,         _'_........./:   ;  /  \      /..\:::
                `+------+        \/        ! -,    _-"   "-_... ,;;:   ! /    \    /....\::
                                           \   -_-"         "-_/;;;;   !/      \  /......\:
                                            \   \             /;;;;'   ;--.___. \/_.__.--;;
                                             \   \           /;;;;      '-_    `:!;;;;;;;' 
                                              '.  \         /;;;'          `-_, :!;;;''    
                                                "-_\_______/;;'                `-!'      
""")
    for i in range(3):
        color = [0, 0, 0]
        color[i] = 255
        np.fill(tuple(color))
        np.write()
        time.sleep(1)

def main():
    shape = Path('shape.txt').read_text().strip()
    leds_per_face, num_faces, layers, sensors_to_face, face_to_sensors, face_positions = get_shape(Path(f'shapes/{shape}.json'))

    np = neopixel.NeoPixel(machine.Pin(18, machine.Pin.OUT), leds_per_face * num_faces)

    init_animation(np)

    initial_state = {
        'animation': None,
        'distances': [(None, 0)] * 5
    }

    state = SharedState(initial_state)
    tasks = []
    tasks.append(run_animations(np, leds_per_face, num_faces, layers,sensors_to_face, face_to_sensors, face_positions, state))
    tasks.append(get_animation_name(state))
    tasks.append(read_sensor(state))
    tasks.append(restart_in_30_minutes())
    asyncio.run(asyncio.gather(*tasks))

if __name__ == '__main__':
    main()

