#! /usr/bin/env python3

import os
import argparse
from pathlib import Path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('shape', type=str)
    args = parser.parse_args()
    
    shape_file = f'shapes/{args.shape}.json'
    if not Path(shape_file).exists():
        print(f'ERROR:Shape file {shape_file} does not exist')
        exit(1)
    
    with open('shape.txt', 'w') as f:
        f.write(args.shape)
    
    try:
        port = os.environ.get('PORT', '/dev/cu.usbserial-210')
        os.system(f"mpremote connect {port} fs cp shape.txt :shape.txt")
        os.system(f"mpremote connect {port} reset")
    finally:
        os.remove('shape.txt')
