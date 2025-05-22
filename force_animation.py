#! /usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path

# Attempt to import ANIMATIONS from the animations package
try:
    # Assuming this script is run from the project root,
    # and 'animations' is a package in the current directory.
    # Ensure animations/__init__.py defines ANIMATIONS list.
    from animations import ANIMATIONS
except ImportError:
    print("ERROR: Could not import 'ANIMATIONS' from the 'animations' package.")
    print("Please ensure that:")
    print("1. You are running this script from the project root directory.")
    print("2. The 'animations' directory exists and is a Python package (contains an __init__.py file).")
    print("3. The 'animations/__init__.py' file defines a list named 'ANIMATIONS'.")
    sys.exit(1)
except Exception as e:
    print(f"An unexpected error occurred during import: {e}")
    sys.exit(1)


def check_animation_exists(animation_name: str) -> bool:
    """
    Checks if the animation name is valid:
    1. It's in the ANIMATIONS list from animations/__init__.py.
    2. The corresponding animation file (e.g., animations/animation_name.py) exists.
    """
    if animation_name not in ANIMATIONS:
        print(f"ERROR: Animation '{animation_name}' is not defined in animations.ANIMATIONS.")
        print(f"Available animations are: {', '.join(ANIMATIONS)}")
        return False
    
    animation_file = Path(f'animations/{animation_name}.py')
    if not animation_file.exists():
        print(f"ERROR: Animation file '{animation_file}' does not exist.")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Force a specific animation on the ESP32 or remove the forced animation.",
        epilog="Example usage:\n"
               "  python force_animation.py my_animation_name\n"
               "  python force_animation.py --remove"
    )
    parser.add_argument(
        'animation_name', 
        type=str, 
        nargs='?', 
        help="Name of the animation to force (must be in animations.ANIMATIONS and have a corresponding .py file)."
    )
    parser.add_argument(
        '--remove', 
        action='store_true', 
        help="Remove the 'force_animation.txt' file from ESP32, disabling any forced animation."
    )
    
    args = parser.parse_args()

    port = os.environ.get('PORT', '/dev/cu.usbserial-210')
    force_file_on_esp = ":force_animation.txt"
    local_force_file_name = "force_animation.txt" # Temporary local file

    operation_done = False

    if args.remove:
        if args.animation_name:
            print("Warning: Animation name was provided with --remove flag. It will be ignored.")
        
        remove_cmd = f"mpremote connect {port} fs rm {force_file_on_esp}"
        print(f"Attempting to remove '{force_file_on_esp}' from ESP32...")
        print(f"Executing: {remove_cmd}")
        status = os.system(remove_cmd)
        
        if status == 0:
            print(f"Successfully removed '{force_file_on_esp}' from ESP32.")
            operation_done = True
        else:
            # mpremote fs rm might return non-zero (e.g., 1) if file doesn't exist.
            # This is not necessarily a critical error for a remove operation.
            print(f"Command to remove '{force_file_on_esp}' finished. mpremote exit code: {status}.")
            print(f"This might mean the file was not found on the ESP32, which is okay for a remove operation.")
            # We consider removal "done" even if file wasn't there, to proceed to reset.
            operation_done = True 

    elif args.animation_name:
        animation_name = args.animation_name
        
        print(f"Validating animation '{animation_name}'...")
        if not check_animation_exists(animation_name):
            sys.exit(1)
        print(f"Validation successful for animation '{animation_name}'.")
            
        local_force_file_path = Path(local_force_file_name)
        try:
            print(f"Creating local '{local_force_file_path}' with animation '{animation_name}'.")
            with open(local_force_file_path, 'w') as f:
                f.write(animation_name)

            copy_cmd = f"mpremote connect {port} fs cp {local_force_file_path} {force_file_on_esp}"
            print(f"Attempting to copy '{local_force_file_path}' to '{force_file_on_esp}' on ESP32...")
            print(f"Executing: {copy_cmd}")
            status = os.system(copy_cmd)

            if status != 0:
                print(f"ERROR: Failed to copy '{local_force_file_path}' to '{force_file_on_esp}' on ESP32.")
                print(f"mpremote exit code: {status}")
                sys.exit(1) 
            print(f"Successfully copied '{animation_name}' to '{force_file_on_esp}' on ESP32.")
            operation_done = True

        finally:
            if local_force_file_path.exists():
                os.remove(local_force_file_path)
                print(f"Removed local temporary file '{local_force_file_path}'.")
    else:
        parser.print_help()
        print("\nERROR: You must provide an animation name or use the --remove flag.")
        sys.exit(1)

    if operation_done:
        reset_cmd = f"mpremote connect {port} reset"
        print(f"Attempting to reset ESP32...")
        print(f"Executing: {reset_cmd}")
        status = os.system(reset_cmd)
        if status != 0:
            print(f"Warning: Failed to reset ESP32. mpremote exit code: {status}")
        else:
            print("ESP32 reset command sent successfully.")
    else:
        print("No operation was performed that requires an ESP32 reset.")

if __name__ == '__main__':
    main() 