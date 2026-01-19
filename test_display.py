#!/usr/bin/env python3
"""
Test script for display feedback system
Simulates loop states and shows display output
"""

import time
from PIL import Image, ImageDraw, ImageFont

# Mock variables for testing
LENGTH = 2205  # About 5 seconds at 44100Hz, 512 chunk
RATE = 44100
CHUNK = 512

# Initialize display (supports both OLED and LCD) with error handling
display = None
display_type = None
try:
    # Try OLED first
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
    for bus in [1, 20, 21]:
        for addr in [0x3C, 0x3D]:
            try:
                serial = i2c(port=bus, address=addr)
                display = ssd1306(serial)
                display_type = 'OLED'
                print(f'OLED display initialized on bus {bus} at 0x{addr:02X}')
                break
            except:
                continue
        if display:
            break
    if not display:
        raise Exception("OLED not found")
except Exception as e:
    print(f'OLED not available: {e}')
    try:
        # Fallback to LCD
        from RPLCD.i2c import CharLCD
        for bus in [1, 20, 21]:
            for addr in [0x27, 0x3F]:
                try:
                    display = CharLCD('PCF8574', addr, port=bus, cols=16, rows=2)
                    display_type = 'LCD'
                    print(f'LCD display initialized on bus {bus} at 0x{addr:02X}')
                    break
                except:
                    continue
            if display:
                break
    except Exception as e2:
        print(f'LCD not available: {e2}')

if not display:
    print("ERROR: No display found for testing!")
    exit(1)

# Mock loop class
class MockLoop:
    def __init__(self):
        self.initialized = False
        self.is_recording = False
        self.is_waiting = False
        self.is_playing = False
        self.readp = 0

# Create mock loops
loops = [MockLoop() for _ in range(4)]

def update_display_status():
    '''Updates display with comprehensive loop and track status'''
    if not display:
        return
    try:
        # Calculate loop position and timing
        loop_time = 0.0
        loop_position = 0.0
        loop_percent = 0
        if LENGTH > 0:
            loop_time = (LENGTH * CHUNK) / RATE  # Total loop time in seconds
            if loops[0].initialized:
                loop_position = (loops[0].readp * CHUNK) / RATE
                loop_percent = int((loops[0].readp / LENGTH) * 100)
        
        # Build track status string
        track_status = ""
        for i in range(4):
            if loops[i].is_recording:
                track_status += "R"
            elif loops[i].is_waiting:
                track_status += "W"
            elif loops[i].is_playing:
                track_status += "P"
            elif loops[i].initialized and not loops[i].is_playing:
                track_status += "M"  # Muted
            else:
                track_status += "-"
        
        if display_type == 'OLED':
            # OLED: 128x64 pixels, can show more info
            image = Image.new('1', (128, 64))
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()
            
            # Line 1: Loop time and position
            if LENGTH > 0:
                line1 = f"Loop: {loop_time:.1f}s"
                if loops[0].initialized:
                    line1 += f" @{loop_percent}%"
            else:
                line1 = "Ready to record"
            draw.text((0, 0), line1, font=font, fill=255)
            
            # Line 2: Track status
            line2 = f"T1234: {track_status}"
            draw.text((0, 16), line2, font=font, fill=255)
            
            # Line 3: Individual track details
            active_tracks = sum(1 for loop in loops if loop.initialized)
            recording_tracks = sum(1 for loop in loops if loop.is_recording)
            waiting_tracks = sum(1 for loop in loops if loop.is_waiting)
            line3 = f"Act:{active_tracks} Rec:{recording_tracks} Wait:{waiting_tracks}"
            draw.text((0, 32), line3, font=font, fill=255)
            
            # Line 4: Countdown for waiting tracks or playback position
            if waiting_tracks > 0 and loops[0].initialized:
                buffers_to_restart = LENGTH - loops[0].readp
                time_to_restart = (buffers_to_restart * CHUNK) / RATE
                line4 = f"Start in {time_to_restart:.1f}s"
                draw.text((0, 48), line4, font=font, fill=255)
            elif loops[0].initialized:
                line4 = f"Pos: {loop_position:.1f}s"
                draw.text((0, 48), line4, font=font, fill=255)
            
            display.image(image)
            display.show()
            
        elif display_type == 'LCD':
            # LCD: 16x2, must be concise
            display.clear()
            
            # Row 1: Loop time and position
            if LENGTH > 0:
                if loops[0].initialized:
                    row1 = f"L:{loop_time:.1f}s {loop_percent:3d}%"
                else:
                    row1 = f"Rec {loop_time:.1f}s"
            else:
                row1 = "Ready          "
            display.cursor_pos = (0, 0)
            display.write_string(row1[:16].ljust(16))
            
            # Row 2: Track status or countdown
            waiting_tracks = sum(1 for loop in loops if loop.is_waiting)
            if waiting_tracks > 0 and loops[0].initialized:
                buffers_to_restart = LENGTH - loops[0].readp
                time_to_restart = (buffers_to_restart * CHUNK) / RATE
                row2 = f"{track_status} >{time_to_restart:4.1f}s"
            else:
                row2 = f"T:{track_status}        "
            display.cursor_pos = (1, 0)
            display.write_string(row2[:16].ljust(16))
            
    except Exception as e:
        print(f'Display error: {e}')

print("\nTesting display feedback system...")
print("=" * 50)

# Test 1: Initial state
print("\n1. Initial state (ready to record)")
update_display_status()
time.sleep(2)

# Test 2: Track 1 initialized and playing
print("2. Track 1 playing (5s loop at 50%)")
loops[0].initialized = True
loops[0].is_playing = True
loops[0].readp = LENGTH // 2  # 50% through
update_display_status()
time.sleep(2)

# Test 3: Track 2 armed (waiting)
print("3. Track 2 armed (waiting to record)")
loops[1].is_waiting = True
loops[0].readp = int(LENGTH * 0.75)  # 75% through
update_display_status()
time.sleep(2)

# Test 4: Track 2 recording
print("4. Track 2 recording")
loops[1].is_waiting = False
loops[1].is_recording = True
loops[1].initialized = True
loops[1].is_playing = True
loops[0].readp = int(LENGTH * 0.25)  # 25% through
update_display_status()
time.sleep(2)

# Test 5: Multiple tracks active
print("5. Multiple tracks - T1 playing, T2 playing, T3 muted, T4 armed")
loops[1].is_recording = False
loops[2].initialized = True
loops[2].is_playing = False  # Muted
loops[3].is_waiting = True
loops[0].readp = int(LENGTH * 0.1)  # 10% through
update_display_status()
time.sleep(2)

# Test 6: All tracks playing
print("6. All tracks playing")
loops[2].is_playing = True
loops[3].is_waiting = False
loops[3].initialized = True
loops[3].is_playing = True
loops[0].readp = int(LENGTH * 0.9)  # 90% through
update_display_status()
time.sleep(2)

print("\n" + "=" * 50)
print("Display test complete!")
print("\nLegend:")
print("  R = Recording")
print("  W = Waiting (armed)")
print("  P = Playing")
print("  M = Muted")
print("  - = Empty")
