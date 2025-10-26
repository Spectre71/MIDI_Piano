# piano MIDI keyboard

import mido
from mido import Message, MidiFile, MidiTrack
import pygame
import sys
import os
import re
import numpy as np
import subprocess

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

# Screen/layout
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Full piano range visuals
KEY_WIDTH = 28
KEY_HEIGHT = 500
START_NOTE = 21  # A0
KEYS = 88        # up to C8 (108)
SCREEN_WIDTH = KEY_WIDTH * KEYS
SCREEN_HEIGHT = KEY_HEIGHT
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Piano MIDI Keyboard")
font = pygame.font.Font(None, 28)
font_small = pygame.font.Font(None, 20)
clock = pygame.time.Clock()

# Sounds - Generate piano-like tones procedurally
KEY_SOUNDS = {}

def generate_piano_tone(midi_note, duration=3.0, sample_rate=44100):
    """Generate a realistic piano-like tone with rich harmonics and natural decay"""
    freq = 440.0 * (2.0 ** ((midi_note - 69) / 12.0))
    
    # Generate time array
    samples = int(duration * sample_rate)
    t = np.linspace(0, duration, samples, False)
    
    # Rich harmonic series with inharmonicity (like real piano strings)
    # Lower notes have more prominent harmonics
    harmonic_strength = 1.0 + (69 - midi_note) / 88.0  # Bass notes richer
    
    wave = np.sin(2 * np.pi * freq * t)  # Fundamental
    wave += 0.6 * np.sin(2 * np.pi * freq * 2.01 * t)  # 2nd harmonic (slight inharmonicity)
    wave += 0.4 * np.sin(2 * np.pi * freq * 3.02 * t)  # 3rd
    wave += 0.25 * np.sin(2 * np.pi * freq * 4.03 * t)  # 4th
    wave += 0.15 * np.sin(2 * np.pi * freq * 5.04 * t)  # 5th
    wave += 0.1 * np.sin(2 * np.pi * freq * 6.05 * t)   # 6th
    wave += 0.08 * np.sin(2 * np.pi * freq * 7.06 * t)  # 7th
    wave += 0.06 * np.sin(2 * np.pi * freq * 8.07 * t)  # 8th
    wave += 0.04 * np.sin(2 * np.pi * freq * 9.08 * t)  # 9th
    wave += 0.03 * np.sin(2 * np.pi * freq * 10.09 * t) # 10th
    wave += 0.02 * np.sin(2 * np.pi * freq * 11.1 * t)  # 11th
    wave += 0.015 * np.sin(2 * np.pi * freq * 12.11 * t) # 12th
    
    # Add subtle metallic timbre for higher notes
    if midi_note > 60:
        brightness = (midi_note - 60) / 48.0
        wave += 0.05 * brightness * np.sin(2 * np.pi * freq * 13.12 * t)
        wave += 0.03 * brightness * np.sin(2 * np.pi * freq * 15.14 * t)
    
    # Natural piano envelope - varies by register
    # Higher notes: faster attack, shorter sustain
    # Lower notes: slower attack, longer sustain
    register_factor = (midi_note - 21) / 87.0  # 0 (bass) to 1 (treble)
    
    attack_time = 0.003 + (1 - register_factor) * 0.015  # 3-18ms
    decay_time = 0.1 + (1 - register_factor) * 0.2       # 100-300ms
    release_time = 0.2 + (1 - register_factor) * 0.8     # 200ms-1s
    
    attack_samples = int(attack_time * sample_rate)
    decay_samples = int(decay_time * sample_rate)
    release_samples = int(release_time * sample_rate)
    sustain_level = 0.4 + (1 - register_factor) * 0.2  # Bass sustains more
    
    envelope = np.ones(samples)
    
    # Sharp attack
    if attack_samples > 0:
        envelope[:attack_samples] = np.linspace(0, 1, attack_samples) ** 0.5  # Slightly curved
    
    # Exponential decay (more natural)
    if decay_samples > 0 and attack_samples + decay_samples < samples:
        decay_curve = np.exp(-3 * np.linspace(0, 1, decay_samples))
        decay_curve = 1 - (1 - sustain_level) * (1 - decay_curve)
        envelope[attack_samples:attack_samples+decay_samples] = decay_curve
    
    # Sustain with slight exponential decay
    sustain_start = attack_samples + decay_samples
    sustain_end = max(sustain_start, samples - release_samples)
    if sustain_end > sustain_start:
        sustain_samples = sustain_end - sustain_start
        sustain_decay = np.exp(-0.5 * np.linspace(0, 1, sustain_samples))
        envelope[sustain_start:sustain_end] = sustain_level * sustain_decay
    
    # Smooth release
    if release_samples > 0 and samples >= release_samples:
        release_curve = np.exp(-4 * np.linspace(0, 1, release_samples))
        envelope[-release_samples:] = envelope[-release_samples] * release_curve
    
    wave = wave * envelope
    
    # Normalize with headroom to prevent clipping
    max_val = np.max(np.abs(wave))
    if max_val > 0:
        wave = wave / max_val * 0.8  # 80% of max to avoid distortion
    
    # Convert to 16-bit PCM BEFORE stereo processing
    wave = (wave * 32767).astype(np.int16)
    
    # Stereo with slight width (panning effect for realism)
    pan = 0.5 + (midi_note - 54) / 108.0 * 0.3  # Subtle stereo spread
    left = (wave.astype(np.float32) * (1 - pan)).astype(np.int16)
    right = (wave.astype(np.float32) * pan).astype(np.int16)
    stereo_wave = np.column_stack((left, right))
    
    return pygame.sndarray.make_sound(stereo_wave)

print("Generating high-quality piano sounds for all keys...")
for i in range(KEYS):
    note = START_NOTE + i
    KEY_SOUNDS[note] = generate_piano_tone(note)
print("Sound generation complete!")

# --- MIDI output (mido preferred, fallback to pygame.midi) ---
midi_out_mido = None
midi_out_pygame = None

try:
    import mido as _mido  # type: ignore
    HAVE_MIDO = True
except Exception:
    HAVE_MIDO = False
    _mido = None

if HAVE_MIDO:
    try:
        out_names = _mido.get_output_names()  # type: ignore[attr-defined]
        if out_names:
            midi_out_mido = _mido.open_output(out_names[0])  # type: ignore[attr-defined]
            print(f"MIDI: using mido -> {out_names[0]}")
        else:
            print("MIDI: no mido output ports found.")
    except Exception as e:
        print(f"MIDI (mido) init failed: {e}")

if midi_out_mido is None:
    try:
        import pygame.midi as pgm
        pgm.init()
        dev_id = pgm.get_default_output_id()
        if dev_id == -1:
            for dev in range(pgm.get_count()):
                info = pgm.get_device_info(dev)
                if info and info[3] == 1:  # is output device
                    dev_id = dev
                    break
        if dev_id != -1:
            midi_out_pygame = pgm.Output(dev_id)
            print(f"MIDI: using pygame.midi -> device {dev_id}")
        else:
            print("MIDI: no pygame.midi output devices found.")
    except Exception as e:
        print(f"MIDI (pygame.midi) init failed: {e}")

def midi_note_on(note: int, velocity: int = 96):
    if midi_out_mido is not None:
        try:
            msg = _mido.Message('note_on', note=note, velocity=velocity)  # type: ignore
            midi_out_mido.send(msg)
        except Exception:
            pass
    elif midi_out_pygame is not None:
        try:
            midi_out_pygame.note_on(note, velocity)
        except Exception:
            pass

def midi_note_off(note: int, velocity: int = 64):
    if midi_out_mido is not None:
        try:
            msg = _mido.Message('note_off', note=note, velocity=velocity)  # type: ignore
            midi_out_mido.send(msg)
        except Exception:
            pass
    elif midi_out_pygame is not None:
        try:
            midi_out_pygame.note_off(note, velocity)
        except Exception:
            pass
# Input state
KEYS_PRESSED = set()           # mouse-pressed keys
PLAYING_SEQ_NOTES = set()      # notes currently playing from sequencer

# Key rendering helpers
BLACK_PCS = {1, 3, 6, 8, 10}
NOTE_NAMES_SHARP = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

def is_black_key(midi_note: int) -> bool:
    return (midi_note % 12) in BLACK_PCS

def midi_to_note_name(midi_note: int) -> str:
    pc = midi_note % 12
    octave = midi_note // 12 - 1
    return f"{NOTE_NAMES_SHARP[pc]}{octave}"

def draw_keyboard(bpm, status_text):
    # Background
    screen.fill((20, 20, 20))  # dark background for contrast

    # Keys
    for i in range(KEYS):
        note = START_NOTE + i
        x = i * KEY_WIDTH
        rect = pygame.Rect(x, 0, KEY_WIDTH, KEY_HEIGHT)

        is_black = is_black_key(note)
        active = (note in KEYS_PRESSED) or (note in PLAYING_SEQ_NOTES)

        if is_black:
            base = (10, 10, 10)
            fill = (40, 40, 80) if active else base  # subtle highlight when active
            border = (200, 200, 200)
            text_color = (255, 255, 255)
        else:
            base = (245, 245, 245)
            fill = (180, 220, 255) if active else base  # highlight when active
            border = (60, 60, 60)
            text_color = (0, 0, 0)  # black text on white keys

        pygame.draw.rect(screen, fill, rect)
        pygame.draw.rect(screen, border, rect, 1)

        # Note name label on each key
        name = midi_to_note_name(note)
        label = font_small.render(name, True, text_color)
        screen.blit(label, (x + 4, KEY_HEIGHT - 22))

    # HUD / Legend panel
    legend_lines = [
        f"BPM: {bpm} | {status_text}",
        "Controls:",
        "SPACE: Play    S: Stop    R: Reload    Up/Down: BPM",
        "Mouse: Click keys to play",
    ]
    pad = 6
    maxw = max(font.size(line)[0] for line in legend_lines)
    total_h = sum(font.size(line)[1] for line in legend_lines) + pad * (len(legend_lines) + 1)
    panel = pygame.Surface((maxw + pad * 2, total_h), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 160))
    y = pad
    for line in legend_lines:
        text = font.render(line, True, (255, 255, 255))
        panel.blit(text, (pad, y))
        y += text.get_height() + pad
    screen.blit(panel, (8, 8))

def play_note(note):
    if note in KEY_SOUNDS:
        KEY_SOUNDS[note].play()
    midi_note_on(note, velocity=96)

def stop_note(note):
    if note in KEY_SOUNDS:
        KEY_SOUNDS[note].stop()
    midi_note_off(note, velocity=64)

# --- Simple Sequencer with 2 tracks (sequence.txt) ---

DURATION_MAP = {
    'w': 4.0,   # whole
    'h': 2.0,   # half
    'q': 1.0,   # quarter
    'e': 0.5,   # eighth
    's': 0.25,  # sixteenth
}

REST_MAP = {
    'R': 4.0,    # whole rest
    'r': 2.0,    # half rest
    'rr': 1.0,   # quarter rest
    'rrr': 0.5,  # eighth rest
    'rrrr': 0.25, # sixteenth rest
}

def note_name_to_midi(token):
    # Accept 'R' or 'rest' for rest
    t = token.strip()
    if t.lower() in ('r', 'rest'):
        return 'rest'
    # Check if it's a shorthand rest (R, r, rr, rrr)
    if t in REST_MAP:
        return 'rest'
    if t.isdigit() or (t.startswith('-') and t[1:].isdigit()):
        val = int(t)
        if not (0 <= val <= 127):
            raise ValueError(f"MIDI note out of range: {val}")
        return val
    # Parse letter + optional accidental + octave, e.g. C#4, Db3, F4
    pcs = {
        'C':0,'C#':1,'Db':1,'D':2,'D#':3,'Eb':3,'E':4,'F':5,'F#':6,'Gb':6,
        'G':7,'G#':8,'Ab':8,'A':9,'A#':10,'Bb':10,'B':11
    }
    if len(t) < 2:
        raise ValueError(f"Invalid note: {t}")
    # Extract pitch class part (could be 1 or 2 chars)
    if len(t) >= 3 and t[1] in ['#', 'b']:
        pc = t[:2]
        octv = t[2:]
    else:
        pc = t[0]
        octv = t[1:]
    if pc not in pcs or not octv.lstrip('-').isdigit():
        raise ValueError(f"Invalid note: {t}")
    midi = (int(octv) + 1) * 12 + pcs[pc]
    if not (0 <= midi <= 127):
        raise ValueError(f"MIDI note out of range: {t} -> {midi}")
    return midi

def parse_duration(token):
    t = token.strip().lower()
    if t in DURATION_MAP:
        return DURATION_MAP[t]
    try:
        return float(t)
    except Exception:
        raise ValueError(f"Invalid duration: {token}")

def parse_note_group(note_tok):
    # Accept: single note, 'note+note+...', or '[note:dur note:dur ...]'
    note_tok = note_tok.strip()
    
    # Bracketed chord with individual durations: [Ab3:h C4:h G4:e]
    if note_tok.startswith('[') and note_tok.endswith(']'):
        inner = note_tok[1:-1]
        items = re.split(r'[,\s]+', inner.strip())
        notes_with_dur = []
        for it in items:
            if not it:
                continue
            if ':' in it:
                # Individual note with duration
                n_tok, d_tok = it.rsplit(':', 1)
                n = note_name_to_midi(n_tok)
                if n != 'rest':
                    dur = parse_duration(d_tok)
                    notes_with_dur.append((n, dur))
            else:
                # Note without duration (error in this context)
                raise ValueError(f"Chord notes must have duration: {it}")
        if not notes_with_dur:
            return 'rest'
        # Return list of (note, duration) tuples
        return notes_with_dur
    
    # Plus-separated chord (all same duration, handled at higher level)
    items = note_tok.split('+')
    notes = []
    for it in items:
        if not it:
            continue
        n = note_name_to_midi(it)
        if n != 'rest':
            notes.append(n)
    if not notes:
        return 'rest'
    notes = sorted(set(notes))
    return notes[0] if len(notes) == 1 else notes

def parse_sequence_line(text):
    # Parse a single track line into [(note_or_chord, beats), ...] and control tokens
    if not text.strip():
        return []
    # Split carefully to preserve bracketed chords
    parts = []
    current = ''
    in_bracket = False
    for char in text:
        if char == '[':
            if current.strip():
                parts.append(current.strip())
                current = ''
            in_bracket = True
            current += char
        elif char == ']':
            in_bracket = False
            current += char
            if current.strip():
                parts.append(current.strip())
                current = ''
        elif char in ',;| \t' and not in_bracket:
            if current.strip():
                parts.append(current.strip())
            current = ''
        else:
            current += char
    if current.strip():
        parts.append(current.strip())

    seq = []
    for part in parts:
        if not part:
            continue

        # Triolé control: Triole:<w|h|q|e|s>
        m = re.match(r'^\s*triole\s*:\s*([whqes])\s*$', part, flags=re.IGNORECASE)
        if m:
            unit = m.group(1).lower()
            seq.append(('__TRIOLE__', DURATION_MAP[unit]))
            continue

        # Standalone rest shorthand (R, r, rr, rrr, rrrr)
        if part in REST_MAP:
            seq.append(('rest', REST_MAP[part]))
            continue

        # Bracketed chord with individual durations
        if part.startswith('[') and part.endswith(']'):
            chord_data = parse_note_group(part)
            if chord_data == 'rest':
                seq.append(('rest', 0.5))
            elif isinstance(chord_data, list) and len(chord_data) > 0 and isinstance(chord_data[0], tuple):
                seq.append((chord_data, None))  # variable-duration chord
            else:
                raise ValueError(f"Invalid bracketed chord: {part}")
            continue

        if ':' not in part:
            raise ValueError(f"Token must be NOTE[:NOTE...]:DUR or rest shorthand or Triole:<unit> -> {part}")
        note_tok, dur_tok = part.rsplit(':', 1)
        note = parse_note_group(note_tok)
        beats = parse_duration(dur_tok)
        seq.append((note, beats))
    return seq

def parse_sequence_file_text(text):
    # Supports:
    #   L: <events...>
    #   R: <events...>
    # If no prefixes are present, treat the whole file as a single 'R' track.
    tracks = {}
    any_labeled = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^([LR]):\s*(.*)$', line, flags=re.IGNORECASE)
        if m:
            any_labeled = True
            label = m.group(1).upper()
            body = m.group(2)
            tracks[label] = parse_sequence_line(body)
        else:
            # Unlabeled content; accumulate into a special key
            tracks.setdefault('_', [])
            tracks['_'].extend(parse_sequence_line(line))
    if any_labeled:
        if 'L' not in tracks:
            tracks['L'] = []
        if 'R' not in tracks:
            tracks['R'] = []
        return {'L': tracks['L'], 'R': tracks['R']}
    else:
        # Single track fallback as Right hand
        return {'R': tracks.get('_', [])}

def _pick_file_dialog():
    """Try native Linux file pickers, fall back to tkinter"""
    # Try zenity (GTK)
    try:
        result = subprocess.run(
            ['zenity', '--file-selection', '--title=Select Sequence File', '--file-filter=Text files | *.txt', '--file-filter=All files | *'],
            capture_output=True, text=True, check=False, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Try kdialog (KDE)
    try:
        result = subprocess.run(
            ['kdialog', '--getopenfilename', os.getcwd(), '*.txt|Text files\n*|All files'],
            capture_output=True, text=True, check=False, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Fallback to tkinter
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        selected = filedialog.askopenfilename(
            title='Select Sequence File',
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            initialdir=os.getcwd()
        )
        root.destroy()
        return selected if selected else None
    except Exception as e:
        print(f"File picker error: {e}")
        return None

def load_sequence_from_file(path=None):
    """Load sequence from file. If path is None, opens file picker dialog."""
    
    # If no path provided, open file picker
    if path is None:
        selected = _pick_file_dialog()
        if selected:
            path = selected
        else:
            # User cancelled or error; try default
            default_path = os.path.join(os.path.dirname(__file__) if '__file__' in globals() else os.getcwd(), 'sequence.txt')
            if os.path.exists(default_path):
                print(f"No file selected. Using default: {default_path}")
                path = default_path
            else:
                print("No file selected and sequence.txt not found. Example:")
                print("  L: C2:q G2:q C3:q [C2 E2 G2]:h")
                print("  R: C4:e E4:e G4:e C5:q R:e C5:e")
                return {'L': [], 'R': []}
    
    # Validate path exists
    if not os.path.exists(path):
        print(f"{path} not found. Example:")
        print("  L: C2:q G2:q C3:q [C2 E2 G2]:h")
        print("  R: C4:e E4:e G4:e C5:q R:e C5:e")
        return {'L': [], 'R': []}
    
    # Load and parse
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        seq = parse_sequence_file_text(text)
        total = sum(len(v) for v in seq.values())
        print(f"Loaded sequence with {total} events from {path}")
        return seq
    except Exception as e:
        print(f"Failed to parse {path}: {e}")
        return {'L': [], 'R': []}

def beats_to_ms(beats, bpm):
    return int((60_000.0 / bpm) * beats)

# ---- Triolé helpers ----
def _event_nominal_beats(event):
    # event is (note_or_chord, beats) where beats can be None for variable chord
    note, beats = event
    if beats is None and isinstance(note, list) and note and isinstance(note[0], tuple):
        # variable-duration chord: use max of its note durations
        return max(d for _, d in note)
    return beats if isinstance(beats, (int, float)) else 0.0

def _compute_triole_scale(seq, start_idx, base_unit):
    # Look ahead to next up to 3 non-control events and compute scaling
    count = 0
    total_nominal = 0.0
    i = start_idx + 1
    while i < len(seq) and count < 3:
        ev = seq[i]
        if isinstance(ev, tuple) and len(ev) == 2 and ev[0] == '__TRIOLE__':
            i += 1
            continue  # skip nested control tokens
        total_nominal += _event_nominal_beats(ev)
        count += 1
        i += 1
    if count == 0 or total_nominal <= 0:
        return 1.0, 0
    # Triplet: compress next 'count' events to span time of two base units
    desired_total = 2.0 * base_unit
    scale = desired_total / total_nominal
    return scale, count

# Sequencer state
BPM = 120
SEQUENCE = load_sequence_from_file("sequence.txt") # Try default on startup
is_playing = False

# Per-track timing state
track_state = {}  # label -> dict(idx, current, next_on_ms, off_ms, finished, trip_scale, trip_remaining)

def sequencer_start():
    global is_playing, track_state
    if not any(SEQUENCE.values()):
        print("No sequence loaded. Press R to reload or create sequence.txt.")
        return
    is_playing = True
    now = pygame.time.get_ticks()
    track_state = {}
    for label, seq in SEQUENCE.items():
        track_state[label] = {
            'idx': -1,
            'current': None,        # None | 'rest' | int | [int,...]
            'next_on_ms': now,      # schedule immediately
            'off_ms': 0,
            'finished': False,
            'len': len(seq),
            'trip_scale': 1.0,
            'trip_remaining': 0,
        }
    PLAYING_SEQ_NOTES.clear()
    print("Playback started.")

def sequencer_stop():
    global is_playing, track_state
    # Stop any notes still sounding
    for n in list(PLAYING_SEQ_NOTES):
        stop_note(n)
    PLAYING_SEQ_NOTES.clear()
    is_playing = False
    track_state = {}
    print("Playback stopped.")

def _stop_current_for_track(state):
    cur = state['current']
    if cur not in (None, 'rest'):
        if isinstance(cur, list):
            for n in cur:
                PLAYING_SEQ_NOTES.discard(n)
                stop_note(n)
        else:
            PLAYING_SEQ_NOTES.discard(cur)
            stop_note(cur)
    state['current'] = None

def sequencer_update():
    if not is_playing:
        return
    now = pygame.time.get_ticks()
    all_finished = True

    for label, seq in SEQUENCE.items():
        st = track_state.get(label)
        if not st or st['finished']:
            continue

        # Turn off if time passed
        if st['current'] not in (None, 'rest') and now >= st['off_ms']:
            _stop_current_for_track(st)

        # Start next if ready
        if st['current'] is None and now >= st['next_on_ms']:
            # Consume any control tokens (e.g., Triolé) before starting a sounding event
            while True:
                st['idx'] += 1
                if st['idx'] >= st['len']:
                    st['finished'] = True
                    break
                ev = seq[st['idx']]
                if isinstance(ev, tuple) and len(ev) == 2 and ev[0] == '__TRIOLE__':
                    base_unit = ev[1]
                    scale, count = _compute_triole_scale(seq, st['idx'], base_unit)
                    st['trip_scale'] = scale
                    st['trip_remaining'] = count
                    # Continue to next token
                    continue
                # Non-control event reached; schedule it
                note, beats = ev

                # Effective duration with Triolé if active
                if beats is None and isinstance(note, list) and note and isinstance(note[0], tuple):
                    # variable-duration chord: scale each note's duration
                    eff_notes = []
                    for n, d in note:
                        d_eff = d * st['trip_scale'] if st['trip_remaining'] > 0 else d
                        eff_notes.append((n, d_eff))
                    max_dur = max(d for _, d in eff_notes)
                    # Start all notes
                    for n, _ in eff_notes:
                        PLAYING_SEQ_NOTES.add(n)
                        play_note(n)
                    st['current'] = [n for n, _ in eff_notes]
                    dur_ms = beats_to_ms(max_dur, BPM)
                    st['off_ms'] = now + dur_ms
                    st['next_on_ms'] = now + dur_ms
                else:
                    # Normal note/chord/rest
                    eff_beats = beats
                    if isinstance(eff_beats, (int, float)) and st['trip_remaining'] > 0:
                        eff_beats = eff_beats * st['trip_scale']
                    dur_ms = beats_to_ms(eff_beats, BPM)
                    if note != 'rest':
                        if isinstance(note, list):
                            for n in note:
                                PLAYING_SEQ_NOTES.add(n)
                                play_note(n)
                        else:
                            PLAYING_SEQ_NOTES.add(note)
                            play_note(note)
                        st['current'] = note
                    else:
                        st['current'] = 'rest'
                    st['off_ms'] = now + dur_ms
                    st['next_on_ms'] = now + dur_ms

                # Consume one of the triolé slots if active
                if st['trip_remaining'] > 0:
                    st['trip_remaining'] -= 1
                    if st['trip_remaining'] == 0:
                        st['trip_scale'] = 1.0
                break  # scheduled one event this tick

        if not st['finished']:
            all_finished = False

    if all_finished:
        sequencer_stop()

# --- Events / Main loop ---

def mouse_down_to_note(pos):
    x, y = pos
    key_index = x // KEY_WIDTH
    if 0 <= key_index < KEYS:
        return START_NOTE + key_index
    return None

def track_status_string():
    if not is_playing or not track_state:
        return "Ready"
    parts = []
    for label, st in sorted(track_state.items()):
        total = st['len']
        cur = min(st['idx'] + 1, total)
        parts.append(f"{label}:{cur}/{total}")
    return "Playing " + " ".join(parts)

# Main loop
while True:
    status = track_status_string()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            # Clean up MIDI backends
            try:
                if midi_out_mido is not None:
                    midi_out_mido.close()
            except Exception:
                pass
            try:
                if midi_out_pygame is not None:
                    midi_out_pygame.close()
                    import pygame.midi as _pgm_quit  # lazy import to avoid top-level requirement
                    _pgm_quit.quit()
            except Exception:
                pass
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                sequencer_start()
            elif event.key == pygame.K_s:
                sequencer_stop()
            elif event.key == pygame.K_r:
                SEQUENCE = load_sequence_from_file() # Opens picker
                print("Sequence reloaded.")
            elif event.key == pygame.K_UP:
                BPM = min(400, BPM + 1)
            elif event.key == pygame.K_DOWN:
                BPM = max(20, BPM - 1)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            note = mouse_down_to_note(event.pos)
            if note is not None:
                KEYS_PRESSED.add(note)
                play_note(note)
        elif event.type == pygame.MOUSEBUTTONUP:
            note = mouse_down_to_note(event.pos)
            if note is not None and note in KEYS_PRESSED:
                KEYS_PRESSED.remove(note)
                stop_note(note)

    sequencer_update()

    screen.fill(BLACK)
    draw_keyboard(BPM, status)
    pygame.display.flip()
    clock.tick(60)