#!/usr/bin/env python3
"""Test if PLAYBUTTON 0 (GPIO 11) is working"""

import time
from gpiozero import Button

print("Testing PLAYBUTTON 0 (GPIO 11)")
print("=" * 50)
print("Press the button assigned to Track 1 PLAY")
print("(Should be GPIO 11 according to code)")
print()

button = Button(11, bounce_time=0.03)

press_count = 0
held_count = 0

def on_press():
    global press_count
    press_count += 1
    print(f"PRESSED! (count: {press_count})")

def on_release():
    print(f"Released")

def on_held():
    global held_count
    held_count += 1
    print(f"HELD! (count: {held_count})")

button.when_pressed = on_press
button.when_released = on_release
button.when_held = on_held

print("Waiting for button presses... (Ctrl+C to exit)")
print("Hold for 2 seconds to trigger 'held' event")
print()

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n\nTest complete!")
    print(f"Total presses: {press_count}")
    print(f"Total holds: {held_count}")
