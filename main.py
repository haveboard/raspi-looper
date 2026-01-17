
print('LOADING...')

import pyaudio
import numpy as np
import time
import os
import threading
from gpiozero import LED, Button

# Try to use LGPIO pin factory for gpiozero if available
from gpiozero import Device
try:
    from gpiozero.pins.lgpio import LGPIOFactory
    Device.pin_factory = LGPIOFactory()
except Exception:
    # Fallback to default pin factory
    pass

debounce_length = 0.03 #length in seconds of button debounce period
hold_time_length = 2.0 #length in seconds to hold button before triggering held event

# Thread lock for LED updates
led_update_lock = threading.Lock()

# Thread lock for display updates to prevent concurrent access
display_update_lock = threading.Lock()

# Initialize display (supports both OLED and LCD) with error handling
display = None
display_type = None
try:
    # Try OLED first (SSD1306 128x64 I2C) - matches gpio_connections.txt
    # Using luma.oled which directly uses smbus2 without Blinka
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
    from PIL import Image, ImageDraw, ImageFont
    # Try I2C bus 1 (GPIO 2/3), then fallback to bus 20/21
    for bus in [1, 20, 21]:
        for addr in [0x3C, 0x3D]:
            try:
                serial = i2c(port=bus, address=addr)
                display = ssd1306(serial)
                display_type = 'OLED'
                print(f'OLED display initialized on bus {bus} at 0x{addr:02X} (3.3V)')
                break
            except:
                continue
        if display:
            break
    if not display:
        raise Exception("OLED not found on any bus")
except Exception as e:
    print(f'OLED not available: {e}')
    try:
        # Fallback to LCD (HD44780 via PCF8574 I2C) - needs 5V
        from RPLCD.i2c import CharLCD
        # Try both common I2C addresses on multiple buses
        for bus in [1, 20, 21]:
            for addr in [0x27, 0x3F]:
                try:
                    display = CharLCD('PCF8574', addr, port=bus, cols=16, rows=2)
                    display_type = 'LCD'
                    print(f'LCD display initialized on bus {bus} at 0x{addr:02X} (needs 5V)')
                    break
                except:
                    continue
            if display:
                break
    except Exception as e2:
        print(f'LCD not available: {e2}')

if not display:
    print("WARNING: No display found - running without display")

PLAYLEDS = (LED(12), LED(16), LED(4), LED(17))
RECLEDS = (LED(27), LED(22), LED(10), LED(9))
PLAYBUTTONS = (Button(11, bounce_time = debounce_length, hold_time = hold_time_length),
              Button(5, bounce_time = debounce_length, hold_time = hold_time_length),
              Button(6, bounce_time = debounce_length, hold_time = hold_time_length),
              Button(13, bounce_time = debounce_length, hold_time = hold_time_length))
RECBUTTONS = (Button(19, bounce_time = debounce_length, hold_time = hold_time_length),
               Button(26, bounce_time = debounce_length, hold_time = hold_time_length),
               Button(21, bounce_time = debounce_length, hold_time = hold_time_length),
               Button(20, bounce_time = debounce_length, hold_time = hold_time_length))


#get configuration (audio settings etc.) from file
settings_file = open('Config/settings.prt', 'r')
parameters = settings_file.readlines()
settings_file.close()

RATE = int(parameters[0]) #sample rate
CHUNK = int(parameters[1]) #buffer size
FORMAT = pyaudio.paInt16 #specifies bit depth (16-bit)
CHANNELS = 1 #mono audio
latency_in_milliseconds = int(parameters[2])
LATENCY = round((latency_in_milliseconds/1000) * (RATE/CHUNK)) #latency in buffers
INDEVICE = int(parameters[3]) #index (per pyaudio) of input device
OUTDEVICE = int(parameters[4]) #index of output device
overshoot_in_milliseconds = int(parameters[5]) #allowance in milliseconds for pressing 'stop recording' late
OVERSHOOT = round((overshoot_in_milliseconds/1000) * (RATE/CHUNK)) #allowance in buffers
MAXLENGTH = int(12582912 / CHUNK) #96mb of audio in total
SAMPLEMAX = 0.9 * (2**15) #maximum possible value for an audio sample (little bit of margin)
LENGTH = 0 #length of the first recording on track 1, all subsequent recordings quantized to a multiple of this.

print(str(RATE) + ' ' +  str(CHUNK))
print('NEW VERSION\nlatency correction (buffers): ' + str(LATENCY))
print('looking for devices ' + str(INDEVICE) + ' and ' + str(OUTDEVICE))

silence = np.zeros([CHUNK], dtype = np.int16) #a buffer containing silence

#mixed output (sum of audio from tracks) is multiplied by output_volume before being played.
#This is updated dynamically as max peak in resultant audio changes
output_volume = np.float16(1.0)

#multiplying by up_ramp and down_ramp gives fade-in and fade-out
down_ramp = np.linspace(1, 0, CHUNK)
up_ramp = np.linspace(0, 1, CHUNK)

def update_display_status():
    '''Updates display with comprehensive loop and track status'''
    if not display:
        return
    
    # Use a lock to prevent concurrent display updates
    if not display_update_lock.acquire(blocking=False):
        return  # Skip update if another thread is already updating
    
    try:
        # Don't update if loops aren't defined yet
        if 'loops' not in globals():
            return
            
        # Calculate loop position and timing
        loop_time = 0.0
        loop_position = 0.0
        loop_percent = 0
        if LENGTH > 0:
            loop_time = (LENGTH * CHUNK) / RATE  # Total loop time in seconds
            if loops[0].initialized and LENGTH > 0:
                # Prevent division by zero and ensure valid readp
                readp = max(0, min(loops[0].readp, LENGTH - 1))
                loop_position = (readp * CHUNK) / RATE
                loop_percent = int((readp / LENGTH) * 100)
        
        # Build track status string - ensure it's always 4 characters
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
            
            # Line 1: Loop time and position with high precision
            if LENGTH > 0:
                line1 = f"Loop: {loop_time:.4f}s"
                if loops[0].initialized:
                    line1 += f" @{loop_percent}%"
            else:
                line1 = "Ready to record"
            draw.text((0, 0), line1, font=font, fill=255)
            
            # Line 2: Track status (R=Recording, W=Waiting, P=Playing, M=Muted, -=Empty)
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
                line4 = f"Start in {time_to_restart:.4f}s"
                draw.text((0, 48), line4, font=font, fill=255)
            elif loops[0].initialized:
                line4 = f"Pos: {loop_position:.4f}s"
                draw.text((0, 48), line4, font=font, fill=255)
            
            display.image(image)
            display.show()
            
        elif display_type == 'LCD':
            # LCD: 16x2, must be concise (keep 1 decimal for space)
            # Don't use clear() - just overwrite with spaces for better reliability
            
            # Row 1: Loop time and position
            if LENGTH > 0:
                if loops[0].initialized:
                    row1 = f"L:{loop_time:.4f}s {loop_percent:2d}%"
                else:
                    row1 = f"Rec {loop_time:.4f}s"
            else:
                row1 = "Ready"
            
            # Ensure string is exactly 16 characters
            row1 = str(row1)[:16].ljust(16)
            
            # Row 2: Track status or countdown
            waiting_tracks = sum(1 for loop in loops if loop.is_waiting)
            if waiting_tracks > 0 and loops[0].initialized:
                buffers_to_restart = LENGTH - loops[0].readp
                time_to_restart = (buffers_to_restart * CHUNK) / RATE
                row2 = f"{track_status}>{time_to_restart:5.4f}"
            else:
                row2 = f"T:{track_status}"
            
            # Ensure string is exactly 16 characters
            row2 = str(row2)[:16].ljust(16)
            
            # Write both rows with position setting for each
            display.cursor_pos = (0, 0)
            display.write_string(row1)
            display.cursor_pos = (1, 0)
            display.write_string(row2)
            
    except Exception as e:
        print(f'Display error: {e}')
        import traceback
        traceback.print_exc()
    finally:
        display_update_lock.release()

def fade_in(buffer):
    '''
    fade_in() applies fade-in to a buffer
    '''
    np.multiply(buffer, up_ramp, out = buffer, casting = 'unsafe')


def fade_out(buffer):
    '''
    fade_out() applies fade-out to a buffer
    '''
    np.multiply(buffer, down_ramp, out = buffer, casting = 'unsafe')

pa = pyaudio.PyAudio()

# Display startup message
if display:
    try:
        if display_type == 'OLED':
            image = Image.new('1', (128, 64))
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()
            draw.text((30, 16), 'RASPI LOOPER', font=font, fill=255)
            draw.text((20, 32), '4-Track Ready', font=font, fill=255)
            display.image(image)
            display.show()
        elif display_type == 'LCD':
            display.clear()
            display.cursor_pos = (0, 0)
            display.write_string('RASPI LOOPER    ')
            display.cursor_pos = (1, 0)
            display.write_string('4-Track Ready   ')
    except Exception as e:
        print(f'Display error: {e}')

class audioloop:
    def __init__(self):
        self.initialized = False
        self.length_factor = 1
        self.length = 0
        #self.main_audio and self.dub_audio contain audio data in arrays of CHUNKs.
        self.main_audio = np.zeros([MAXLENGTH, CHUNK], dtype = np.int16)
        #self.dub_audio contains the latest recorded dub. Clearing this achieves undo.
        self.dub_audio = np.zeros([MAXLENGTH, CHUNK], dtype = np.int16)
        self.readp = 0
        self.writep = 0
        self.is_recording = False
        self.is_playing = False
        self.is_waiting = False
        self.last_buffer_recorded = 0 #index of last buffer added
        self.preceding_buffer = np.zeros([CHUNK], dtype = np.int16)
        """
        Dub ratio must be reduced with each overdub to keep all overdubs at the same level while preventing clipping.
        first overdub is attenuated by a factor of 0.9, second by 0.81, etc.
        each time the existing audio is attenuated by a factor of 0.9.
        """
        self.dub_ratio = 1.0

    def increment_pointers(self):
        '''
        increment_pointers() increments pointers and, when restarting while recording, advances dub ratio
        '''
        if self.readp == self.length - 1:
            self.readp = 0
            if self.is_recording:
                self.dub_ratio = self.dub_ratio * 0.9
                print(self.dub_ratio)
        else:
            self.readp = self.readp + 1
        self.writep = (self.writep + 1) % self.length

    def initialize(self):
        '''
        initialize() raises self.length to closest integer multiple of LENGTH and initializes read and write pointers
        '''
        print('initialize called')
        if self.initialized:
            print('redundant initialization')
            return
        self.writep = self.length - 1
        self.last_buffer_recorded = self.writep
        self.length_factor = (int((self.length - OVERSHOOT) / LENGTH) + 1)
        self.length = self.length_factor * LENGTH
        print('length ' + str(self.length))
        print('last buffer recorded ' + str(self.last_buffer_recorded))
        #crossfade
        fade_out(self.main_audio[self.last_buffer_recorded]) #fade out the last recorded buffer
        preceding_buffer_copy = np.copy(self.preceding_buffer)
        fade_in(preceding_buffer_copy)
        self.main_audio[self.length - 1, :] += preceding_buffer_copy[:]
        #audio should be written ahead of where it is being read from, to compensate for input+output latency
        self.readp = (self.writep + LATENCY) % self.length
        self.initialized = True
        self.is_playing = True
        self.increment_pointers()

    def add_buffer(self, data):
        '''
        add_buffer() appends a new buffer unless loop is filled to MAXLENGTH
        expected to only be called before initialization
        '''
        if self.length >= (MAXLENGTH - 1):
            self.length = 0
            print('loop full')
            return
        self.main_audio[self.length, :] = np.copy(data)
        self.length = self.length + 1

    def toggle_mute(self):
        if self.is_playing:
            self.is_playing = False
        else:
            self.is_playing = True

    def is_restarting(self):
        if not self.initialized:
            return False
        if self.readp == 0:
            return True
        return False

    def read(self):
        '''
        read() reads and returns a buffer of audio from the loop

        if not initialized: Do nothing
        if initialized but muted: Just increment pointers
        if initialized and playing: Read audio from the loop and increment pointers
        '''        
        if not self.initialized:
            return(silence)
        
        if not self.is_playing:
            self.increment_pointers()
            return(silence)
        
        tmp = self.readp
        self.increment_pointers()
        return(self.main_audio[tmp, :] + self.dub_audio[tmp, :])
    
    def dub(self, data, fade_in = False, fade_out = False):
        '''
        dub() overdubs an incoming buffer of audio to the loop at writep
        
        at writep:
        first, the buffer from dub_audio is mixed into main_audio
        next, the buffer in dub_audio is overwritten with the incoming buffer
        '''
        if not self.initialized:
            return
        datadump = np.copy(data)
        self.main_audio[self.writep, :] = self.main_audio[self.writep, :] * 0.9 + self.dub_audio[self.writep, :] * self.dub_ratio
        self.dub_audio[self.writep, :] = datadump[:]

    def clear(self):
        '''
        clear() clears the loop so that a new loop of the same or a different length can be recorded on the track
        '''
        self.main_audio = np.zeros([MAXLENGTH, CHUNK], dtype = np.int16)
        self.dub_audio = np.zeros([MAXLENGTH, CHUNK], dtype = np.int16)
        self.initialized = False
        self.is_playing = False
        self.is_recording = False
        self.is_waiting = False
        self.length_factor = 1
        self.length = 0
        self.readp = 0
        self.writep = 0
        self.last_buffer_recorded = 0
        self.preceding_buffer = np.zeros([CHUNK], dtype = np.int16)

    def undo(self):
        '''
        undo() resets dub_audio to silence
        '''
        self.dub_audio = np.zeros([MAXLENGTH, CHUNK], dtype = np.int16)
        self.is_recording = False
        self.is_waiting = False

    def clear_or_undo(self):
        '''
        clear if muted, undo if playing.
        '''
        if self.is_playing:
            self.undo()
        else:
            self.clear()
    
    def start_recording(self, previous_buffer):
        self.is_recording = True
        self.is_waiting = False
        self.preceding_buffer = np.copy(previous_buffer)

    def set_recording(self):
        '''
        set_recording() either starts or stops recording

        if initialized and recording, stop recording (dubbing)
        if uninitialized and recording, stop recording (appending) and initialize
        if initialized and not recording, set as "waiting to record"
        '''
        print('set_recording called')
        already_recording = False

        #if chosen track is currently recording, flag it
        if self.is_recording:
            already_recording = True

        #turn off recording
        if self.is_recording and not self.initialized:
            self.initialize()
        self.is_recording = False
        self.is_waiting = False

        #unless flagged, schedule recording. If chosen track was recording, then stop recording
        #like a toggle but with delayed enabling and instant disabling
        if not already_recording:
            self.is_waiting = True

#defining four audio loops. loops[0] is the master loop.
loops = (audioloop(), audioloop(), audioloop(), audioloop())

#while looping, prev_rec_buffer keeps track of the audio buffer recorded before the current one
prev_rec_buffer = np.zeros([CHUNK], dtype = np.int16)

def update_volume():
    '''
    update output volume to prevent mixing distortion due to sample overflow
    slow to run, so should be called on a different thread (e.g. a button callback function)
    '''
    global output_volume
    try:
        # Only calculate peak if loops are initialized to avoid accessing uninitialized data
        if not any(loop.initialized for loop in loops):
            return
        
        peak = np.max(
                      np.abs(
                              loops[0].main_audio.astype(np.int32)[:][:]
                            + loops[1].main_audio.astype(np.int32)[:][:]
                            + loops[2].main_audio.astype(np.int32)[:][:]
                            + loops[3].main_audio.astype(np.int32)[:][:]
                            + loops[0].dub_audio.astype(np.int32)[:][:]
                            + loops[1].dub_audio.astype(np.int32)[:][:]
                            + loops[2].dub_audio.astype(np.int32)[:][:]
                            + loops[3].dub_audio.astype(np.int32)[:][:]
                            )
                     )
        print('peak = ' + str(peak))
        if peak > SAMPLEMAX:
            output_volume = SAMPLEMAX / peak
        else:
            output_volume = 1
        print('output volume = ' + str(output_volume))
    except Exception as e:
        print(f'Error in update_volume: {e}')

def show_status():
    '''
    show_status() checks which loops are recording/playing and lights up LEDs accordingly
    Also updates display with current status
    '''
    with led_update_lock:
        for i in range(4):
            if loops[i].is_recording:
                RECLEDS[i].on()
            else:
                RECLEDS[i].off()
            if loops[i].is_playing:
                PLAYLEDS[i].on()
            else:
                PLAYLEDS[i].off()
    
    # Update display when LEDs change (skip if display is busy)
    if display:
        try:
            update_display_status()
        except Exception as e:
            print(f'Display error in show_status: {e}')  # Don't let display errors interrupt the program

setup_is_recording = False #set to True when track 1 recording button is first pressed
setup_donerecording = False #set to true when first track 1 recording is done

play_buffer = np.zeros([CHUNK], dtype = np.int16) #buffer to hold mixed audio from all 4 tracks
display_update_counter = 0  # Counter to throttle display updates

def looping_callback(in_data, frame_count, time_info, status):
    global play_buffer
    global prev_rec_buffer
    global setup_donerecording
    global setup_is_recording
    global LENGTH
    global display_update_counter
    
    current_rec_buffer = np.right_shift(np.frombuffer(in_data, dtype = np.int16), 2) #some input attenuation for overdub headroom purposes
    
    # Update display periodically (less often for LCD to avoid timing issues)
    display_update_counter += 1
    update_interval = 30 if display_type == 'LCD' else 10  # LCD updates slower
    if display_update_counter >= update_interval:
        display_update_counter = 0
        if display and setup_donerecording:  # Only update during active looping
            try:
                update_display_status()
            except Exception as e:
                print(f'Display update error in callback: {e}')  # Don't let display errors interrupt audio
    
    #SETUP: FIRST RECORDING
    #if setup is not done i.e. if the master loop hasn't been recorded to yet
    if not setup_donerecording:
        #if setup is currently recording, that recording action happens in the following lines
        if setup_is_recording:
            #if the max allowed loop length is exceeded, stop recording and start looping
            if LENGTH >= MAXLENGTH:
                print('Overflow')
                setup_donerecording = True
                setup_is_recording = False
                return(silence, pyaudio.paContinue)
            #otherwise append incoming audio to master loop, increment LENGTH and continue
            loops[0].add_buffer(current_rec_buffer)
            LENGTH = LENGTH + 1
            return(silence, pyaudio.paContinue)
        #if setup not done and not currently happening then just wait
        else:
            return(silence, pyaudio.paContinue)
    #execution ony reaches here if setup (first loop record and set LENGTH) finished.
    #when master loop restarts, start recording on any other tracks that are waiting
    if loops[0].is_restarting():
        #update_volume()
        for loop in loops:
            if loop.is_waiting:
                loop.start_recording(prev_rec_buffer)
                print('Recording...')
    #if master loop is waiting just start recording without checking restart
    if loops[0].is_waiting and not loops[0].initialized:
            loops[0].start_recording(prev_rec_buffer)
    #if a loop is recording, check initialization and accordingly append or overdub
    for loop in loops:
        if loop.is_recording:
            if loop.initialized:
                loop.dub(current_rec_buffer)
            else:
                loop.add_buffer(current_rec_buffer)
    #add to play_buffer only one-fourth of each audio signal times the output_volume
    play_buffer[:] = np.multiply((
                                   loops[0].read().astype(np.int32)[:]
                                 + loops[1].read().astype(np.int32)[:]
                                 + loops[2].read().astype(np.int32)[:]
                                 + loops[3].read().astype(np.int32)[:]
                                 ), output_volume, out= None, casting = 'unsafe').astype(np.int16)
    #current buffer will serve as previous in next iteration
    prev_rec_buffer = np.copy(current_rec_buffer)
    #play mixed audio and move on to next iteration
    return(play_buffer, pyaudio.paContinue)

#now initializing looping_stream (the only audio stream)
looping_stream = pa.open(
    format = FORMAT,
    channels = CHANNELS,
    rate = RATE,
    input = True,
    output = True,
    input_device_index = INDEVICE,
    output_device_index = OUTDEVICE,
    frames_per_buffer = CHUNK,
    start = True,
    stream_callback = looping_callback
)

#audio stream has now been started and the callback function is running in a background thread.
#first, we give the stream some time to properly start up
time.sleep(3)
#then we turn on all lights to indicate that looper is ready to start looping
print('ready')
for led in RECLEDS:
    led.on()
for led in PLAYLEDS:
    led.on()

#once all LEDs are on, we wait for the master loop record button to be pressed
# Wait a bit for GPIO to stabilize after LED changes
time.sleep(0.3)
print('Waiting for first button press...')

# Show ready message on display
if display:
    try:
        if display_type == 'OLED':
            image = Image.new('1', (128, 64))
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()
            draw.text((10, 8), 'Press RECORD 1', font=font, fill=255)
            draw.text((10, 24), 'to start first', font=font, fill=255)
            draw.text((10, 40), 'loop recording', font=font, fill=255)
            display.image(image)
            display.show()
        elif display_type == 'LCD':
            display.clear()
            display.cursor_pos = (0, 0)
            display.write_string('Press REC1 to   ')
            display.cursor_pos = (1, 0)
            display.write_string('start recording ')
    except Exception as e:
        print(f'Display error: {e}')

RECBUTTONS[0].wait_for_press()
print('Button pressed! Starting recording...')

# Show recording message
if display:
    try:
        if display_type == 'OLED':
            image = Image.new('1', (128, 64))
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()
            draw.text((20, 16), 'RECORDING...', font=font, fill=255)
            draw.text((10, 32), 'Track 1 Active', font=font, fill=255)
            display.image(image)
            display.show()
        elif display_type == 'LCD':
            display.clear()
            display.cursor_pos = (0, 0)
            display.write_string('RECORDING...    ')
            display.cursor_pos = (1, 0)
            display.write_string('Track 1 Active  ')
    except Exception as e:
        print(f'Display error: {e}')

#when the button is pressed, set the flag... looping_callback will see this flag. Also start recording on track 1
setup_is_recording = True
loops[0].start_recording(prev_rec_buffer)

#turn off all LEDs except master loop record
for i in range(1, 4):
    RECLEDS[i].off()
for led in PLAYLEDS:
    led.off()

#allow time for button release, otherwise pressing the button once will start and stop the recording
time.sleep(0.5)
print('Waiting for second button press to stop recording...')

# Update display to show waiting for stop
if display:
    try:
        if display_type == 'OLED':
            image = Image.new('1', (128, 64))
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()
            draw.text((15, 8), 'RECORDING T1...', font=font, fill=255)
            draw.text((5, 24), 'Press REC1 again', font=font, fill=255)
            draw.text((25, 40), 'to finish', font=font, fill=255)
            display.image(image)
            display.show()
        elif display_type == 'LCD':
            display.cursor_pos = (0, 0)
            display.write_string('Recording T1... ')
            display.cursor_pos = (1, 0)
            display.write_string('Press to finish ')
    except Exception as e:
        print(f'Display error: {e}')

#now wait for button to be pressed again, then stop recording and initialize master loop
RECBUTTONS[0].wait_for_press()
print('Button pressed! Stopping recording...')

# Show loop initialization message
if display:
    try:
        if display_type == 'OLED':
            image = Image.new('1', (128, 64))
            draw = ImageDraw.Draw(image)
            font = ImageFont.load_default()
            draw.text((15, 16), 'Initializing', font=font, fill=255)
            draw.text((25, 32), 'Loop...', font=font, fill=255)
            display.image(image)
            display.show()
        elif display_type == 'LCD':
            display.cursor_pos = (0, 0)
            display.write_string('Initializing    ')
            display.cursor_pos = (1, 0)
            display.write_string('Loop...         ')
    except Exception as e:
        print(f'Display error: {e}')

setup_is_recording = False
setup_donerecording = True
print(LENGTH)
loops[0].initialize()
print('length is ' + str(LENGTH))

#stop recording on track 1, light LEDs appropriately, then allow time for button release
loops[0].set_recording()
show_status()
time.sleep(0.5)

#UI do everything else

finished = False
#calling finish() will set finished flag, allowing program to break from loop at end of script and exit
jam_session_active = False  # Flag to prevent premature exit
def finish():
    global finished
    if not jam_session_active:
        print('Ignoring finish - jam session not yet active')
        return
    finished = True

#restart_looper() restarts this python script
def restart_looper():
    if not jam_session_active:
        print('Ignoring restart - jam session not yet active')
        return
    pa.terminate() #needed to free audio device for reuse
    os.execlp('python3', 'python3', 'main.py') #replaces current process with a new instance of the same script

# Wrapper functions for button callbacks to catch exceptions
def safe_clear_or_undo(loop_index):
    try:
        print(f'DEBUG: clear_or_undo called for loop {loop_index}')
        loops[loop_index].clear_or_undo()
        show_status()
    except Exception as e:
        print(f'Error in clear_or_undo for loop {loop_index}: {e}')

def safe_set_recording(loop_index):
    try:
        print(f'DEBUG: set_recording called for loop {loop_index}')
        loops[loop_index].set_recording()
        show_status()
    except Exception as e:
        print(f'Error in set_recording for loop {loop_index}: {e}')

def safe_toggle_mute(loop_index):
    try:
        print(f'DEBUG: toggle_mute called for loop {loop_index}')
        loops[loop_index].toggle_mute()
        show_status()
    except Exception as e:
        print(f'Error in toggle_mute for loop {loop_index}: {e}')

def safe_update_volume():
    try:
        update_volume()
    except Exception as e:
        print(f'Error in update_volume: {e}')

def safe_finish():
    try:
        print('!!! FINISH CALLED - Exiting program !!!')
        finish()
    except Exception as e:
        print(f'Error in finish: {e}')

def safe_restart():
    try:
        print('!!! RESTART CALLED - Restarting program !!!')
        restart_looper()
    except Exception as e:
        print(f'Error in restart_looper: {e}')

#now defining functions of all the buttons during jam session...

for i in range(4):
    RECBUTTONS[i].when_held = lambda idx=i: safe_clear_or_undo(idx)
    RECBUTTONS[i].when_pressed = lambda idx=i: safe_set_recording(idx)
    RECBUTTONS[i].when_released = safe_update_volume
    PLAYBUTTONS[i].when_pressed = lambda idx=i: safe_toggle_mute(idx)

# Wait for all buttons to be released before attaching finish/restart handlers
time.sleep(0.5)
print('Ready for jam session! Hold PLAYBUTTON 4 (GPIO 20) for 2 sec to exit, or PLAYBUTTON 1 (GPIO 19) to restart')

# Don't attach finish/restart handlers yet - wait for jam session to stabilize
jam_session_active = False

#this while loop runs during the jam session.
try:
    # Wait a few loop iterations before enabling exit/restart to avoid spurious triggers
    for _ in range(30):  # Wait 3 seconds (30 * 0.1)
        show_status()
        time.sleep(0.1)
    
    # Check button states before enabling exit/restart
    print('Checking button states...')
    stuck_buttons = []
    for i in range(4):
        if PLAYBUTTONS[i].is_pressed:
            print(f'WARNING: PLAYBUTTON {i} (GPIO {[19,26,21,20][i]}) is stuck pressed!')
            stuck_buttons.append(f'PLAY{i}')
        if RECBUTTONS[i].is_pressed:
            print(f'WARNING: RECBUTTON {i} (GPIO {[11,5,6,13][i]}) is stuck pressed!')
            stuck_buttons.append(f'REC{i}')
    
    if stuck_buttons:
        print(f'Stuck buttons detected: {", ".join(stuck_buttons)}')
        print('Hardware issue detected - buttons may not work correctly')
        print('Check your wiring: buttons should connect GPIO to GROUND when pressed')
    
    # Now safe to enable finish/restart (only if button 3 is not stuck)
    jam_session_active = True
    if not PLAYBUTTONS[3].is_pressed:
        PLAYBUTTONS[3].when_held = safe_finish
        print('Exit handler enabled on PLAYBUTTON 3')
    else:
        print('PLAYBUTTON 3 exit handler DISABLED (button stuck)')
    PLAYBUTTONS[0].when_held = safe_restart
    print('Restart handler enabled on PLAYBUTTON 0')
    print('Program running - use CTRL+C to force exit')
    
    while not finished:
        show_status()
        time.sleep(0.1)
except Exception as e:
    print(f'Error during jam session: {e}')
    import traceback
    traceback.print_exc()
finally:
    pa.terminate()
    print('Done...')
