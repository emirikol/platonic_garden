from pathlib import Path
import json
from typing import Tuple, List
import neopixel

class Shape:
    def __init__(self, file_path: Path):
        self.name = file_path.stem  # Gets filename without extension
        data = json.loads(file_path.read_text())
        
        self.leds_per_face = data.get('led_per_face')
        faces_data = data.get('faces')
        sensors = data.get('sensors')
        
        if self.leds_per_face is None or faces_data is None:
            raise ValueError(f"Invalid shape data in {file_path}")
            
        self.num_faces = len(faces_data)
        self.layers = self._get_layers(faces_data)
        self.sensors_to_face = [[face for face in range(len(faces_data)) if i in faces_data[face]['sensors']] for i in range(sensors)]
        self.face_to_sensors = [face['sensors'] for face in faces_data]
        self.face_positions = [face['pos'] for face in faces_data]

    def _get_layers(self, shape_faces: List[dict]) -> Tuple[Tuple[int, ...], ...]:
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

    def set_face_color(self, np: neopixel.NeoPixel, face_index: int, color: Tuple[int, int, int]) -> None:
        """Set all LEDs in a face to a specific color."""
        face_offset = self.leds_per_face * face_index
        for i in range(self.leds_per_face):
            np[face_offset + i] = color 