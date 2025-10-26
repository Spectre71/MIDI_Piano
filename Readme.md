# Piano Keyboard – User Manual

A minimal piano practice/sequencer app with a full 88-key visual keyboard (A0–C8), two-handed sequencing, chords, rests, triplet (Triolé) timing, and generated piano-like sound.

## Features
- 88-key keyboard visualization with proper black/white keys and note labels.
- Click any key to play it; active keys highlight.
- Procedurally generated tones (no .wav files required).
- Optional MIDI out via mido if a port is available.
- Two tracks (Left and Right hand) with independent rhythms.
- Chords:
  - Shared-duration chords: C3+E3+G3:q
  - Per-note duration chords: [Ab3:h C4:h G4:e]
- Rests:
  - Shorthand rests: R (whole), r (half), rr (quarter), rrr (eighth), rrrr (sixteenth)
  - Classic: rest:q or R:e
- Triolé timing: compress the next 3 events to the time of 2 units (e.g., Triole:e)

## Requirements
- Python 3.10+
- Linux
- pip packages: pygame, numpy, mido (optional: python-rtmidi for MIDI output)

Install:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run
```bash
source venv/bin/activate
python3 piano.py
```

## Controls (GUI)
- SPACE: Play sequence
- S: Stop playback
- R: Reload sequence.txt
- Up/Down: Increase/Decrease BPM
- Mouse: Click keys to play/stop

A legend is shown in the top-left of the window.

## Sequence File
Path: sequence.txt (same folder as piano.py)

Format supports labeled tracks:
```
L: <left hand events...>
R: <right hand events...>
```
If no L:/R: labels are present, the entire file is treated as a single right-hand track.

### Notes
- Names: C4, C#4, Db4, … B (A0–C8). Sharps (#) and flats (b) supported.
- MIDI numbers (0–127) also accepted, e.g., 60.
- Range outside 21–108 is allowed in parsing, but audio is generated for 21–108.

### Durations
- Symbols: w=4, h=2, q=1, e=0.5, s=0.25 (beats)
- Numeric: 1.5, 0.75, etc.

Specify as NOTE:DUR, e.g.:
```
C4:q   D#4:e   60:1.5
```

### Rests
- Shorthand tokens (standalone):
  - R = whole (4.0 beats)
  - r = half (2.0)
  - rr = quarter (1.0)
  - rrr = eighth (0.5)
  - rrrr = sixteenth (0.25)
- Or with explicit duration: rest:e, R:q, etc.

Examples:
```
rr    rrrr    rest:q
```

### Chords
- Shared-duration chord (all notes same duration):
  ```
  C3+E3+G3:q
  ```
- Per-note durations in brackets:
  ```
  [Ab3:h C4:h G4:e]
  ```
  All notes start together; each ends at its own duration. The next event begins after the longest of the chord’s durations.

Tip: Ensure a space or delimiter exists between tokens. For example:
```
rrr [Eb3:h Ab3:h C4:h]
```
(not “rrr[Eb3…”).

### Triolé (Triplet Feel)
Use a control token to compress the next 3 events so they collectively take the time of two units:
```
Triole:<w|h|q|e|s>
```
- Triole:e makes the next three events together last as long as two eighths (each gets scaled so the three fit into 1.0 beats if base unit is e=0.5).
- Applies to notes, rests, shared-duration chords, and per-note-duration chords (each note’s duration is scaled).
- Only affects the next three non-control events on that track.

Example:
```
R: Triole:e B3:e C4:e Eb4:e F4:q
```

## Examples

Basic two-hand example:
```
L: C2:q G2:q C3:q [C2 E2 G2]:h
R: C4:e E4:e G4:e C5:q rrr C5:e
```

Per-note-duration chord:
```
R: [Ab3:h C4:h G4:e] F#4:e F4:e E4:e
```

Triplet feel over three eighths:
```
R: Triole:e B3:e C4:e Eb4:e
```

## Tips & Troubleshooting
- No sound:
  - Ensure numpy and pygame installed.
  - Pygame mixer initializes at 44.1kHz, 16-bit, stereo; check system audio.
- MIDI output:
  - If no MIDI ports are found, the app prints a warning and still plays internal sounds.
- Parsing errors:
  - Ensure tokens are separated by spaces, commas, semicolons, or pipes.
  - Bracketed chords must be closed: [C4:e E4:e G4:e]
  - For per-note chords, each inner note must include a duration.
- Performance:
  - Large windows (88 keys) can be wide; use your desktop zoom or adjust KEY_WIDTH/HEIGHT in code if needed.

## Roadmap
- Metronome click
- Sustain pedal (damper) simulation
- Swing quantization
- Export to MIDI
- Velocity control per note
- Looping sections and markers

## License / Credits
- Internal tone generator uses synthesized harmonics and envelopes.
- MIDI via mido; audio via pygame.
