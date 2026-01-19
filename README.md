# raspi-looper
Simple 4 track looper for Raspberry Pi. Uses pyaudio.

## Hardware Setup
### Components
- Raspberry Pi
- USB sound card
- 8 Buttons
- 8 LEDs
- Audio jacks, wires and connectors to taste
- **Optional:** I2C Display (OLED SSD1306 or LCD HD44780 with PCF8574 backpack)

### Connections
- Buttons and LEDs connect to GPIO (see gpio_connections.txt).
- Sound card plugs into full-size USB port on Raspberry Pi.
- Looper input goes to sound card input AND to looper output 1 ("LIVE").
- Soundcard output goes to looper output 2 ("LOOPS").

#### Display Wiring (Optional)
**OLED (SSD1306 128x64) - 3.3V:**
- VCC → 3.3V (Pin 1 or 17)
- GND → Ground
- SDA → GPIO2 (Pin 3)
- SCL → GPIO3 (Pin 5)

**LCD (HD44780 with PCF8574 I2C backpack) - 5V:**
- VCC → **5V** (Pin 2 or 4) - **NOT 3.3V!**
- GND → Ground
- SDA → GPIO2 (Pin 3)
- SCL → GPIO3 (Pin 5)

#### Rotary Encoder Wiring (Optional)
**KY-040 or similar rotary encoder:**
- CLK (A) → GPIO23
- DT (B) → GPIO24
- SW (Button) → GPIO25
- + → 3.3V
- GND → Ground

See GPIO connections table and wiring diagram.

## Software Setup
### Basic
1. Install system dependencies:
   ```bash
   sudo apt install python3-pyaudio python3-numpy python3-gpiozero python3-lgpio i2c-tools
   ```

2. Install Python packages:
   ```bash
   pip install --break-system-packages -r requirements.txt
   ```

3. **(Optional)** Enable I2C for display support:
   ```bash
   bash enable_i2c.sh
   sudo reboot
   ```
   After reboot, verify I2C devices are detected:
   ```bash
   i2cdetect -y 1
   ```
   - OLED shows at 0x3C or 0x3D
   - LCD shows at 0x27 or 0x3F
   - Adjust LCD contrast using the blue potentiometer on the I2C backpack if needed

4. Uninstall pulseaudio (if present)

5. Configure audio devices by running `python3 settings.py`

6. **(Optional)** Install as a system service to auto-start on boot:
   ```bash
   ./install-service.sh
   ```
   This will configure the looper to start automatically on boot and restart if it crashes.

### Optional/Troubleshooting
- Uninstall unnecessary software, disable GUI (speed up boot time)
- Adjust sound levels in alsamixer (if signal is too quiet/loud)
- Turn off WiFi (reduce noise/interference)
- The looper works without a display - it's purely optional for status information

## User Manual
### Begin Session
- Press Track 1 Record Button to start looping. Track 1 will start recording.
- Press Track 1 Record Button to stop recording. Track 1 will now loop.

### During Session
- Press Record Button to arm a track for recording or overdubbing. Recording will start on the next loop of Track 1.
- Press Record Button again to stop recording or overdubbing.
- Press play button to mute or unmute track.
- While track is playing, hold Record button to undo last overdub.
- While track is muted, hold Record button to clear track.

### After Session
- Hold Track 1 Play Button to start new session.
- Hold Track 4 Play Button to exit the looper script.

### Rotary Encoder Menu (Optional)
If you have a rotary encoder connected (GPIO23/24/25):
- **Press button** to cycle through menu items (VOL/TRIM/CLK)
- **Rotate** to adjust the selected parameter:
  - **VOL**: Adjust output volume (10% to 150%)
  - **TRIM**: Fine-tune loop length in milliseconds (±100ms range after recording first loop)
  - **CLK**: Toggle click track on/off

The encoder is polled continuously in the main loop for responsive control without relying on interrupts.

## Features
- 4 independent audio tracks with overdubbing
- Automatic volume adjustment to prevent clipping
- Undo last overdub per track
- Optional I2C display support (OLED 128x64 or LCD 20x4)
- Optional rotary encoder menu for real-time control:
  - Volume adjustment (10% to 150%)
  - Loop trim for fine-tuning timing (±100ms)
  - Click track toggle
- Latency compensation
- Fade in/out for smooth loop transitions
- Auto-start on boot with systemd service

## System Service Management
After installing with `./install-service.sh`, use these commands:

**Service Control:**
```bash
sudo systemctl status raspi-looper   # Check if running
sudo systemctl stop raspi-looper     # Stop service
sudo systemctl start raspi-looper    # Start service
sudo systemctl restart raspi-looper  # Restart service
sudo systemctl disable raspi-looper  # Disable autostart on boot
sudo systemctl enable raspi-looper   # Re-enable autostart on boot
```

**View Logs:**
```bash
# Connect to live logs (follow mode - shows real-time output)
sudo journalctl -u raspi-looper -f

# View last 50 lines
sudo journalctl -u raspi-looper -n 50

# View logs since boot
sudo journalctl -u raspi-looper -b

# View logs from specific time
sudo journalctl -u raspi-looper --since "10 minutes ago"
```

**Manual Run (for testing):**
```bash
# Stop the service first
sudo systemctl stop raspi-looper
# Run manually
cd ~/raspi-looper
python3 main.py
```

## Notes
- Display support is optional - the looper works fine without it
- Supports both OLED (3.3V) and LCD 20x4 (5V) displays automatically
- Rotary encoder is optional for volume/trim/click control
- GPIO pin assignments corrected from original - see gpio_connections.txt
- Button mapping: PLAY and REC buttons were swapped in code vs. documentation

### TODO
- Update wiring diagram with correct GPIO pins