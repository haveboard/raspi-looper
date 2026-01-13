# raspi-looper
Simple 4 track looper for Raspberry Pi. Uses pyaudio.

## Hardware Setup
### Components
- Raspberry Pi
- USB sound card
- 8 Buttons
- 8 LEDs
- Audio jacks, wires and connectors to taste

### Connections
- Buttons and LEDs connect to GPIO.
- Sound card plugs into full-size USB port on Raspberry Pi.
- Looper input goes to sound card input AND to looper output 1 ("LIVE").
- Soundcard output goes to looper output 2 ("LOOPS").

See GPIO connections table and wiring diagram.

## Software Setup
### Basic
- Install dependencies: `sudo apt install python3-pyaudio python3-numpy python3-gpiozero python3-lgpio`
- Uninstall pulseaudio (if present)
- Download this repository
- Configure audio devices by running `python3 settings.py`
- Set main.py to start on boot (run main.py as sudo)

### Optional/Troubleshooting
- Uninstall unnecessary software, disable GUI (speed up boot time)
- Adjust sound levels in alsamixer (if signal is too quiet/loud)
- Turn off WiFi (reduce noise/interference)

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

### TODO
- Update wiring diagram with correct GPIO pins