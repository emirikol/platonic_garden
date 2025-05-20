import asyncio
from copy import deepcopy
from typing import Optional, Dict, Any, Callable

class SharedState:
    def __init__(self, initial: Optional[Dict[Any, Any]] = None):
        self._data: Optional[Dict[Any, Any]] = deepcopy(initial) if initial is not None else {}

    async def get_unsafe(self) -> Optional[Dict[Any, Any]]:
        return self._data
    
    async def get(self) -> Optional[Dict[Any, Any]]:
        return deepcopy(self._data)

    async def update(self, key: str, value: Any) -> None:
        if self._data is None:
            self._data = {}
        self._data[key] = value


async def read_until_null_terminator(reader):
    buffer = bytearray()
    while True:
        byte = await reader.read(1)  # Reads 1 byte, returns a bytes object like b'\x00' or b'a'

        if byte == b'\x00':
            return bytes(buffer)

        buffer.append(byte[0])


def get_colors() -> list[tuple[int, int, int]]:
    possible_values = [127, 255]
    colors = []

    colors = [
        (r, g, b)
        for r in possible_values
        for g in possible_values
        for b in possible_values
        if r!=g and g!=b
    ]
    return colors
