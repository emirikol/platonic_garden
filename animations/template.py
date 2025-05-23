import asyncio
from utils import SharedState
from shape import Shape
import neopixel

async def animate(
        np: neopixel.NeoPixel,
        shape: Shape,
        stop_event: asyncio.Event,
        state: SharedState
) -> None:
    """
    Template for animation functions using the Shape class.
    
    Args:
        np: The NeoPixel object to control the LEDs
        shape: Shape object containing all shape-related data:
            - shape.name: Name of the shape (filename without .json extension)
            - shape.leds_per_face: Number of LEDs per face
            - shape.num_faces: Total number of faces
            - shape.layers: Tuple of tuples containing face IDs organized by layers
            - shape.sensors_to_face: List mapping sensors to faces they affect
            - shape.face_to_sensors: List mapping faces to their associated sensors
            - shape.face_positions: List of face positions in 3D space
            - shape.set_face_color(np, face_id, color): Method to set all LEDs in a face to a specific color
        stop_event: Event to signal when the animation should stop
        state: Shared state object for communication between components
    """
    # Example usage:
    while not stop_event.is_set():
        # Access shape properties
        for layer in shape.layers:
            for face_id in layer:
                if face_id >= shape.num_faces:
                    continue
                    
                # Get sensors for this face
                face_sensors = shape.face_to_sensors[face_id]
                face_position = shape.face_positions[face_id]
                
                # Set face color example
                shape.set_face_color(np, face_id, (255, 0, 0))
                
        np.write()
        await asyncio.sleep_ms(50)  # Example frame delay
