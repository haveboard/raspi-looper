# Display Feedback System

## Overview
The raspi-looper now includes comprehensive real-time display feedback showing loop status, track states, countdown timers, and more.

## Display Information

### LCD (16x2) Display Format
**Row 1:** Loop time and position
- `L:5.2s  50%` - Loop is 5.2 seconds, currently at 50%
- `Rec 3.1s` - Currently recording, 3.1 seconds recorded
- `Ready` - Ready to start recording

**Row 2:** Track status and countdown
- `T:RPWM >2.3s` - Track states + countdown to start
- `T:PPPM` - Track states only
  - R = Recording
  - P = Playing
  - W = Waiting (armed for recording)
  - M = Muted
  - - = Empty/inactive

### OLED (128x64) Display Format
**Line 1:** Loop time and position
- `Loop: 5.2s @50%` - Playing at 50% position
- `Ready to record` - Idle state

**Line 2:** Track status per track
- `T1234: RPWM` - Individual track states

**Line 3:** Summary statistics
- `Act:3 Rec:1 Wait:1` - Active, Recording, and Waiting track counts

**Line 4:** Position or countdown
- `Start in 2.3s` - When tracks are armed (waiting)
- `Pos: 2.6s` - Current playback position

## Display Updates

### During Setup
1. **Startup:** "RASPI LOOPER / 4-Track Ready"
2. **Waiting for first record:** "Press REC1 to start recording"
3. **Recording first loop:** "RECORDING... / Track 1 Active"
4. **Ready to stop:** "Recording T1... / Press to finish"
5. **Initializing:** "Initializing Loop..."

### During Jam Session
- **Automatic updates:** Display refreshes ~2-3 times per second during looping
- **Button press updates:** Immediate feedback when buttons are pressed
- **Real-time countdown:** Shows time until armed tracks start recording
- **Position tracking:** Shows current position in the loop
- **Track states:** Visual indication of all 4 track states

## Technical Details

### Update Frequency
- Display updates every 10 audio buffers (~0.3-0.5 seconds)
- Immediate updates on button presses (record, play, mute)
- Non-blocking: Display errors won't interrupt audio

### Display Function
`update_display_status()` - Main function that:
- Calculates loop timing and position
- Determines track states (R/P/W/M/-)
- Formats output for OLED or LCD
- Shows countdown for armed tracks
- Handles errors gracefully

### Integration Points
1. **looping_callback:** Periodic updates during audio processing
2. **show_status:** Updates when LED states change
3. **Button callbacks:** Implicit via show_status() calls
4. **Setup sequence:** Manual updates at key points

## Track Status Legend
- **R (Recording):** Track is actively recording
- **P (Playing):** Track is playing back
- **W (Waiting):** Track is armed, will start recording next loop
- **M (Muted):** Track has content but is muted
- **- (Empty):** Track is empty/inactive

## Usage Example

### LCD Display During Session
```
L:8.7s  23%      <- Loop is 8.7s, at 23% position
T:P-W-  >6.2s    <- T1 playing, T3 armed, starts in 6.2s
```

### OLED Display During Session
```
Loop: 8.7s @23%
T1234: P-W-
Act:1 Rec:0 Wait:1
Start in 6.2s
```

## Benefits
- **Visual feedback:** Always know what's happening
- **Countdown timers:** Know exactly when recording starts
- **Track overview:** See all track states at a glance
- **Loop timing:** Monitor loop length and position
- **Professional feel:** Real-time status makes operation intuitive
