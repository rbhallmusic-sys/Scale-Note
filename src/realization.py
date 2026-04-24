"""
Deterministic SATB realization engine.

Input: Chord progression (symbols or pitch sets)
Output: Initial SATB voicing (intentionally rough for correction loop)

Strategy:
  1. Parse chord → pitch set
  2. Assign pitches to voices using heuristics
  3. Ensure voice ranges + alignment
  4. Shape soprano melody
  5. Return Score
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Set
from music_model import Score, Voice, Note, VOICE_RANGES, VOICE_ORDER
from pitch_utils import semitones_between


# =========================================================
# Chord Database (MIDI pitch classes)
# =========================================================

CHORD_TEMPLATES = {
    # Major triads
    "C": [0, 4, 7],
    "C major": [0, 4, 7],
    "D": [2, 6, 9],
    "D major": [2, 6, 9],
    "E": [4, 8, 11],
    "E major": [4, 8, 11],
    "F": [5, 9, 0],
    "F major": [5, 9, 0],
    "G": [7, 11, 2],
    "G major": [7, 11, 2],
    "A": [9, 1, 4],
    "A major": [9, 1, 4],
    "B": [11, 3, 6],
    "B major": [11, 3, 6],
    
    # Minor triads
    "c": [0, 3, 7],
    "C minor": [0, 3, 7],
    "d": [2, 5, 9],
    "D minor": [2, 5, 9],
    "e": [4, 7, 11],
    "E minor": [4, 7, 11],
    "f": [5, 8, 0],
    "F minor": [5, 8, 0],
    "g": [7, 10, 2],
    "G minor": [7, 10, 2],
    "a": [9, 0, 4],
    "A minor": [9, 0, 4],
    "b": [11, 2, 6],
    "B minor": [11, 2, 6],
    
    # Dominant 7ths
    "G7": [7, 11, 2, 5],
    "D7": [2, 6, 9, 0],
    "A7": [9, 1, 4, 8],
    
    # Diminished
    "o": [0, 3, 6],
    "dim": [0, 3, 6],
}


# =========================================================
# Pitch Class Utilities
# =========================================================

def pc_to_midi(pitch_class: int, octave: int) -> int:
    """Convert pitch class (0-11) + octave to MIDI."""
    return pitch_class + (octave * 12)


def midi_to_pc(midi: int) -> int:
    """Convert MIDI to pitch class (0-11)."""
    return midi % 12


def expand_chord(chord_pcs: List[int], bass_octave: int = 3) -> Dict[str, int]:
    """
    Expand pitch-class chord into concrete octaves (MIDI).
    
    Returns dict:
      {
        "root": 48,     # Bass octave
        "third": 52,    # Bass octave or +1
        "fifth": 55,    # Bass octave or +1
        ...
      }
    
    Assumes root = pcs[0], third = pcs[1], fifth = pcs[2], etc.
    """
    chord_dict = {}
    
    if len(chord_pcs) > 0:
        chord_dict["root"] = pc_to_midi(chord_pcs[0], bass_octave)
    if len(chord_pcs) > 1:
        # Third in next octave if needed to avoid crossing
        third_midi = pc_to_midi(chord_pcs[1], bass_octave)
        if third_midi <= chord_dict["root"]:
            third_midi += 12
        chord_dict["third"] = third_midi
    if len(chord_pcs) > 2:
        # Fifth above third
        fifth_midi = pc_to_midi(chord_pcs[2], bass_octave)
        if fifth_midi <= chord_dict.get("third", chord_dict["root"]):
            fifth_midi += 12
        chord_dict["fifth"] = fifth_midi
    if len(chord_pcs) > 3:
        # Seventh (if present)
        seventh_midi = pc_to_midi(chord_pcs[3], bass_octave)
        if seventh_midi <= chord_dict.get("fifth", chord_dict.get("third", chord_dict["root"])):
            seventh_midi += 12
        chord_dict["seventh"] = seventh_midi
    
    return chord_dict


# =========================================================
# Voice Assignment Heuristics
# =========================================================

def get_chord_tones(chord_symbol: str) -> List[int]:
    """
    Parse chord symbol → pitch classes (0-11).
    
    Examples:
      "C major" → [0, 4, 7]
      "G7" → [7, 11, 2, 5]
    """
    if chord_symbol not in CHORD_TEMPLATES:
        raise ValueError(f"Unknown chord: {chord_symbol}")
    return CHORD_TEMPLATES[chord_symbol]


def find_closest_note_in_range(
    target: int, 
    voice_name: str, 
    available_pitches: List[int]
) -> int:
    """
    Find pitch from available_pitches closest to target, within voice range.
    
    Args:
        target: Target MIDI pitch
        voice_name: "S", "A", "T", or "B"
        available_pitches: List of MIDI pitches to choose from
    
    Returns:
        MIDI pitch (from available_pitches, within range)
    """
    low, high = VOICE_RANGES[voice_name]
    
    candidates = [p for p in available_pitches if low <= p <= high]
    if not candidates:
        # Fallback: find closest even if out of range
        candidates = available_pitches
    
    if not candidates:
        raise ValueError(f"No pitches available for {voice_name}")
    
    # Return closest to target
    return min(candidates, key=lambda p: abs(p - target))


def realize_chord(
    chord_symbol: str,
    bass_octave: int = 3,
    prev_soprano: Optional[int] = None,
    prev_alto: Optional[int] = None,
    prev_tenor: Optional[int] = None,
) -> Dict[str, int]:
    """
    Realize a single chord into SATB pitches.
    
    Args:
        chord_symbol: "C major", "G7", etc.
        bass_octave: Base octave for voicing (default 3 = tenor octave)
        prev_soprano/alto/tenor: Previous voice pitches (for smooth voice leading)
    
    Returns:
        {"S": 72, "A": 64, "T": 60, "B": 48}
    """
    chord_pcs = get_chord_tones(chord_symbol)
    chord_dict = expand_chord(chord_pcs, bass_octave)
    
    # Extract available pitches
    pitches = list(chord_dict.values())
    
    # ===== BASS: Root =====
    bass = chord_dict["root"]
    remaining_pitches = [p for p in pitches if p != bass]
    
    # ===== TENOR: Closest above bass, prefer stepwise from prev =====
    tenor_candidates = [p for p in remaining_pitches if VOICE_RANGES["T"][0] <= p <= VOICE_RANGES["T"][1]]
    if not tenor_candidates:
        tenor_candidates = remaining_pitches
    
    if prev_tenor:
        tenor = min(tenor_candidates, key=lambda p: abs(p - prev_tenor))
    else:
        tenor = min(tenor_candidates)
    
    remaining_pitches = [p for p in remaining_pitches if p != tenor]
    
    # ===== ALTO: Fill gap, prefer stepwise from prev =====
    alto_candidates = [p for p in remaining_pitches if VOICE_RANGES["A"][0] <= p <= VOICE_RANGES["A"][1]]
    if not alto_candidates:
        alto_candidates = remaining_pitches
    
    if prev_alto:
        alto = min(alto_candidates, key=lambda p: abs(p - prev_alto))
    else:
        alto = min(alto_candidates)
    
    remaining_pitches = [p for p in remaining_pitches if p != alto]
    
    # ===== SOPRANO: Highest available, shape melody =====
    soprano_candidates = [p for p in remaining_pitches if VOICE_RANGES["S"][0] <= p <= VOICE_RANGES["S"][1]]
    if not soprano_candidates:
        # Fallback: add doubled root or third
        soprano_candidates = [p + 12 for p in [chord_dict["root"], chord_dict.get("third", chord_dict["root"])] 
                             if VOICE_RANGES["S"][0] <= p + 12 <= VOICE_RANGES["S"][1]]
    
    if not soprano_candidates:
        soprano_candidates = remaining_pitches
    
    if prev_soprano:
        # Prefer stepwise motion, but allow leap
        stepwise = [p for p in soprano_candidates if abs(p - prev_soprano) <= 2]
        if stepwise:
            soprano = min(stepwise, key=lambda p: abs(p - prev_soprano))
        else:
            soprano = min(soprano_candidates, key=lambda p: abs(p - prev_soprano))
    else:
        soprano = max(soprano_candidates)  # Start high
    
    return {
        "S": soprano,
        "A": alto,
        "T": tenor,
        "B": bass,
    }


# =========================================================
# Main Realization Engine
# =========================================================

def realize_progression(
    chord_symbols: List[str],
    key: str = "C major",
    meter: str = "4/4",
    duration: float = 1.0,
    bass_octave: int = 3,
) -> Score:
    """
    Realize a chord progression into SATB score.
    
    Args:
        chord_symbols: ["C major", "F major", "G7", "C major"]
        key: Key signature (for context, not enforced)
        meter: Time signature
        duration: Note duration (in quarter notes)
        bass_octave: Base octave for voicing
    
    Returns:
        Score object with four voices aligned
    """
    
    if not chord_symbols:
        raise ValueError("Chord progression cannot be empty")
    
    # Realize each chord, tracking previous notes for voice leading
    soprano_notes = []
    alto_notes = []
    tenor_notes = []
    bass_notes = []
    
    prev_soprano = None
    prev_alto = None
    prev_tenor = None
    
    for chord_symbol in chord_symbols:
        voicing = realize_chord(
            chord_symbol,
            bass_octave=bass_octave,
            prev_soprano=prev_soprano,
            prev_alto=prev_alto,
            prev_tenor=prev_tenor,
        )
        
        soprano_notes.append(Note(midi=voicing["S"], duration=duration))
        alto_notes.append(Note(midi=voicing["A"], duration=duration))
        tenor_notes.append(Note(midi=voicing["T"], duration=duration))
        bass_notes.append(Note(midi=voicing["B"], duration=duration))
        
        prev_soprano = voicing["S"]
        prev_alto = voicing["A"]
        prev_tenor = voicing["T"]
    
    # Construct Score
    score = Score(
        voices={
            "S": Voice(name="S", notes=soprano_notes),
            "A": Voice(name="A", notes=alto_notes),
            "T": Voice(name="T", notes=tenor_notes),
            "B": Voice(name="B", notes=bass_notes),
        },
        key=key,
        meter=meter,
    )
    
    return score


# =========================================================
# Example Usage
# =========================================================

if __name__ == "__main__":
    # Simple progression: I-IV-V-I in C major
    progression = ["C major", "F major", "G major", "C major"]
    
    score = realize_progression(progression)
    print(f"Generated score: {score}")
    print(f"Number of chords: {score.num_chords()}")
    
    # Print each chord
    for i in range(score.num_chords()):
        s = score.voices["S"].notes[i].midi
        a = score.voices["A"].notes[i].midi
        t = score.voices["T"].notes[i].midi
        b = score.voices["B"].notes[i].midi
        print(f"Chord {i}: S={s}, A={a}, T={t}, B={b}")
