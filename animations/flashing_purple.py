import asyncio
import time
from animations.utils import set_face_color
from utils import SharedState

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
    
    num_steps = 100
    layer_ratio = num_steps / len(layers)
    reverse_start_step = num_steps - 1
    minimum_intensity = 50
    frame_time_ms = 1000/30
    
    # Framerate tracking variables
    total_frames = 0
    start_time = time.time()
    
    async def process_animation_step(step_index):
        nonlocal total_frames
        frame_start = time.time_ns()
        
        distances = (await state.get()).get("distances")
        if stop_event.is_set():
            return True  # Signal to stop
        
        # First pass - set base colors
        for j in range(len(layers)):
            layer_location = j * layer_ratio
            distance = int(abs(step_index - layer_location))
            intensity = max(minimum_intensity, 255 - distance*30)
            layer_color = (intensity, 0, intensity)
            for face in layers[j]:
                set_face_color(np, leds_per_face, face, layer_color)
    
        # Second pass - apply temperature adjustments
        for j in range(len(layers)):
            layer_location = j * layer_ratio
            distance = int(abs(step_index - layer_location))
            intensity = max(minimum_intensity, 255 - distance*30)
            
            if len(layers[j]) != 1:
                for face_index in range(len(layers[j])):
                    if distances is not None and face_index < len(distances) and distances[face_index][0] is not None: 
                        # Get temperature from the tuple (distance, temperature)
                        face = layers[j][face_index]
                        sensor_temp = max([distances[i][1] for i in face_to_sensors[face]] + [0])
                        layer_color = (intensity, 0, int(intensity*((255-sensor_temp)/255)))
                        set_face_color(np, leds_per_face, layers[j][face_index], layer_color)
            else:
                # Compute the average temperature from distances
                if distances is not None and len(distances) > 0:
                    avg_temp = sum(reading[1] for reading in distances) / len(distances)
                    layer_color = (intensity, 0, int(intensity*((255-avg_temp)/255)))
                    set_face_color(np, leds_per_face, layers[j][0], layer_color)

        np.write()
        
        # Track frames
        total_frames += 1
        if total_frames % 100 == 0:  # Update every 100 frames
            elapsed_time = time.time() - start_time
            fps = total_frames / elapsed_time
            print(f"Average framerate: {fps:.2f} FPS")
            
        await asyncio.sleep_ms(int(frame_time_ms - (time.time_ns() - frame_start)/1000000))
        return False  # Continue animation
    
    while True:
        # Forward animation
        for i in range(num_steps):
            should_stop = await process_animation_step(i)
            if should_stop:
                return
                
        # Reverse animation
        for i in range(reverse_start_step, -1, -1):
            should_stop = await process_animation_step(i)
            if should_stop:
                return

