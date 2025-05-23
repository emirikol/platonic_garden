from typing import Tuple

def get_all_colors() -> list[tuple[int, int, int]]:
    possible_values = [0,127, 255]
    colors = []

    colors = [
        (r, g, b)
        for r in possible_values
        for g in possible_values
        for b in possible_values
        if (not r == g == b) and (r == 0 or g == 0 or b == 0)
    ]

    return colors
