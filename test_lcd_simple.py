#!/usr/bin/env python3
"""Simple LCD test without clear()"""
import time

try:
    from RPLCD.i2c import CharLCD
    lcd = CharLCD('PCF8574', 0x27, port=1, cols=16, rows=2)
    
    print("Testing LCD without using clear()...")
    
    # Test 1: Simple overwrite
    print("Test 1: Writing text")
    lcd.cursor_pos = (0, 0)
    lcd.write_string("Test Line 1     ")
    lcd.cursor_pos = (1, 0)
    lcd.write_string("Test Line 2     ")
    time.sleep(2)
    
    # Test 2: Update with different text (no clear)
    print("Test 2: Overwriting")
    lcd.cursor_pos = (0, 0)
    lcd.write_string("Updated Line 1  ")
    lcd.cursor_pos = (1, 0)
    lcd.write_string("Updated Line 2  ")
    time.sleep(2)
    
    # Test 3: Simulate loop display
    print("Test 3: Simulating loop display")
    for i in range(10):
        row1 = f"L:5.2s  {i*10:3d}%   "
        row2 = f"T:P---          "
        
        lcd.cursor_pos = (0, 0)
        lcd.write_string(row1[:16])
        lcd.cursor_pos = (1, 0)
        lcd.write_string(row2[:16])
        time.sleep(0.5)
    
    print("Test complete - display should show loop info")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
