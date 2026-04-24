"""
Pitch and interval utilities for music theory calculations.

- MIDI ↔ note name conversion
- Interval identification
- Parallel motion detection (5ths, octaves)
- Range validation
"""

from typing import Tuple, List
from music_model import VOICE_RANGES, VOICE_ORDER, Note, Voice, Score


# MIDI to note name mapping
MIDI_TO_NOTE = {
    0: "C0", 1: "C#0", 2: "D0", 3: "D#0", 4: "E0", 5: "F0", 6: "F#0", 7: "G0", 8: "G#0", 9: "A0", 10: "A#0", 11: "B0",
    12: "C1", 13: "C#1", 14: "D1", 15: "D#1", 16: "E1", 17: "F1", 18: "F#1", 19: "G1", 20: "G#1", 21: "A1", 22: "A#1", 23: "B1",
    24: "C2", 25: "C#2", 26: "D2", 27: "D#2", 28: "E2", 29: "F2", 30: "F#2", 31: "G2", 32: "G#2", 33: "A2", 34: "A#2", 35: "B2",
    36: "C3", 37: "C#3", 38: "D3", 39: "D#3", 40: "E3", 41: "F3", 42: "F#3", 43: "G3", 44: "G#3", 45: "A3", 46: "A#3", 47: "B3",
    48: "C4", 49: "C#4", 50: "D4", 51: "D#4", 52: "E4", 53: "F4", 54: "F#4", 55: "G4", 56: "G#4", 57: "A4", 58: "A#4", 59: "B4",
    60: "C5", 61: "C#5", 62: "D5", 63: "D#5", 64: "E5", 65: "F5", 66: "F#5", 67: "G5", 68: "G#5", 69: "A5", 70: "A#5", 71: "B5",
    72: "C6", 73: "C#6", 74: "D6", 75: "D#6", 76: "E6", 77: "F6", 78: "F#6", 79: "G6", 80: "G#6", 81: "A6", 82: "A#6", 83: "B6",
    84: "C7", 85: "C#7", 86: "D7", 87: "D#7", 88: "E7", 89: "F7", 90: "F#7", 91: "G7", 92: "G#7", 93: "A7", 94: "A#7", 95: "B7",
}

# Reverse lookup: note name → MIDI (simplified, no enharmonics)
NOTE_TO_MIDI = {v: k for k, v in MIDI_TO_NOTE.items()}


def midi_to_name(midi: int) -> str:
    """Convert MIDI number to note name (e.g., 60 -> 'C5')."""
    if midi not in MIDI_TO_NOTE:
        raise ValueError(f"MIDI {midi} out of range")
    return MIDI_TO_NOTE[midi]


def semitones_between(midi1: int, midi2: int) -> int:
    """
    Return semitones from midi1 to midi2.
    Positive = upward, negative = downward.
    """
    return midi2 - midi1


def interval_name(semitones: int) -> str:
    """
    Return interval name from semitone count.
    E.g., 0 -> "unison", 7 -> "perfect 5th", 12 -> "octave"
    """
    interval_map = {
        0: "unison",
        1: "minor 2nd",
        2: "major 2nd",
        3: "minor 3rd",
        4: "major 3rd",
        5: "perfect 4th",
        6: "tritone",
        7: "perfect 5th",
        8: "minor 6th",
        9: "major 6th",
        10: "minor 7th",
        11: "major 7th",
        12: "octave",
    }
    # Handle negative intervals (downward)
    abs_semi = abs(semitones) % 12
    name = interval_map.get(abs_semi, f"unknown ({semitones})")
    if semitones < 0:
        return f"(down) {name}"
    return name


def is_perfect_fifth(semitones: int) -> bool:
    """Check if interval is a perfect 5th (7 semitones)."""
    return abs(semitones) % 12 == 7


def is_perfect_octave(semitones: int) -> bool:
    """Check if interval is a perfect octave (12 semitones)."""
    return abs(semitones) % 12 == 0 and semitones != 0


def is_in_range(midi: int, voice_name: str) -> bool:
    """Check if MIDI note is in valid range for voice."""
    if voice_name not in VOICE_RANGES:
        raise ValueError(f"Invalid voice: {voice_name}")
    low, high = VOICE_RANGES[voice_name]
    return low <= midi <= high


def voice_range(voice_name: str) -> Tuple[int, int]:
    """Return (low, high) MIDI range for voice."""
    return VOICE_RANGES[voice_name]


def has_parallel_perfect_fifth(midi1a: int, midi1b: int, midi2a: int, midi2b: int) -> bool:
    """
    Detect parallel perfect 5th between two voices across two chords.
    
    Args:
        midi1a, midi1b: Two notes in first chord
        midi2a, midi2b: Two notes in second chord
    
    Returns:
        True if both intervals are perfect 5ths in same direction
    """
    interval1 = semitones_between(midi1a, midi1b)
    interval2 = semitones_between(midi2a, midi2b)
    
    if not (is_perfect_fifth(interval1) and is_perfect_fifth(interval2)):
        return False
    
    # Check same direction (both up or both down)
    return (interval1 > 0) == (interval2 > 0)


def has_parallel_octave(midi1a: int, midi1b: int, midi2a: int, midi2b: int) -> bool:
    """
    Detect parallel perfect octave between two voices across two chords.
    
    Args:
        midi1a, midi1b: Two notes in first chord
        midi2a, midi2b: Two notes in second chord
    
    Returns:
        True if both intervals are perfect octaves in same direction
    """
    interval1 = semitones_between(midi1a, midi1b)
    interval2 = semitones_between(midi2a, midi2b)
    
    if not (is_perfect_octave(interval1) and is_perfect_octave(interval2)):
        return False
    
    # Check same direction (both up or both down)
    return (interval1 > 0) == (interval2 > 0)


def get_chord_pitches(score: Score, chord_idx: int) -> dict:
    """
    Extract MIDI pitches for all voices in a chord.
    
    Returns:
        {"S": 72, "A": 64, "T": 60, "B": 48}
    """
    if chord_idx < 0 or chord_idx >= score.num_chords():
        raise ValueError(f"Chord index {chord_idx} out of range")
    
    pitches = {}
    for voice_name in VOICE_ORDER:
        pitches[voice_name] = score.voices[voice_name].notes[chord_idx].midi
    return pitches


# Example usage
if __name__ == "__main__":
    print(f"Middle C (MIDI 60) = {midi_to_name(60)}")
    print(f"A4 (MIDI 57) = {midi_to_name(57)}")
    
    # C to G (perfect 5th, 7 semitones)
    print(f"\nC5 (60) to G5 (67): {semitones_between(60, 67)} semitones = {interval_name(7)}")
    print(f"Is perfect 5th? {is_perfect_fifth(7)}")
    
    # Check range
    print(f"\nC5 (60) in soprano range? {is_in_range(60, 'S')}")
    print(f"E2 (40) in bass range? {is_in_range(40, 'B')}")
    
    # Parallel motion
    print(f"\nParallel 5th (C-G → D-A)? {has_parallel_perfect_fifth(60, 67, 62, 69)}")
    print(f"Parallel octave (C → C, C → D)? {has_parallel_octave(60, 60, 60, 62)}")
