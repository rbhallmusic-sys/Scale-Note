"""
Clean, minimal data structures for SATB music system.

- Note: MIDI pitch + duration
- Voice: Named collection of Notes (S, A, T, B)
- Score: Four voices + key + meter
"""

from dataclasses import dataclass, field
from typing import Dict, List


# Constants
VOICE_RANGES = {
    "S": (60, 81),   # Soprano: Middle C to A5
    "A": (55, 74),   # Alto: F3 to D5
    "T": (48, 69),   # Tenor: C3 to A4
    "B": (40, 64),   # Bass: E2 to E4
}

VOICE_ORDER = ["S", "A", "T", "B"]


@dataclass
class Note:
    """
    A single note in the score.
    
    Args:
        midi: MIDI note number (0-127), where 60 = Middle C
        duration: Duration in quarter notes (default 1.0 = quarter note)
    """
    midi: int
    duration: float = 1.0
    
    def __post_init__(self):
        """Validate MIDI range."""
        if not 0 <= self.midi <= 127:
            raise ValueError(f"MIDI note must be 0-127, got {self.midi}")
        if self.duration <= 0:
            raise ValueError(f"Duration must be positive, got {self.duration}")
    
    def __repr__(self) -> str:
        return f"Note(midi={self.midi}, dur={self.duration})"


@dataclass
class Voice:
    """
    A single voice in SATB (Soprano, Alto, Tenor, Bass).
    
    Args:
        name: Voice identifier ("S", "A", "T", "B")
        notes: List of Note objects
    """
    name: str
    notes: List[Note] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate voice name."""
        if self.name not in VOICE_ORDER:
            raise ValueError(f"Voice name must be one of {VOICE_ORDER}, got {self.name}")
    
    def __len__(self) -> int:
        return len(self.notes)
    
    def __repr__(self) -> str:
        return f"Voice(name='{self.name}', notes={len(self.notes)})"


@dataclass
class Score:
    """
    A complete SATB score.
    
    Args:
        voices: Dict with keys "S", "A", "T", "B" mapping to Voice objects
        key: Key signature (e.g., "C major", "G major")
        meter: Time signature (e.g., "4/4", "3/4")
    """
    voices: Dict[str, Voice]
    key: str
    meter: str
    
    def __post_init__(self):
        """Validate all required voices present and same length."""
        # Check all voices present
        for voice_name in VOICE_ORDER:
            if voice_name not in self.voices:
                raise ValueError(f"Score must include voice '{voice_name}'")
        
        # Check all voices same length
        lengths = [len(self.voices[name]) for name in VOICE_ORDER]
        if len(set(lengths)) > 1:
            raise ValueError(
                f"All voices must have same length. Got: "
                f"{dict(zip(VOICE_ORDER, lengths))}"
            )
    
    def num_chords(self) -> int:
        """Return the number of chords (harmonic units) = soprano length."""
        return len(self.voices["S"])
    
    def __repr__(self) -> str:
        return (
            f"Score(key='{self.key}', meter='{self.meter}', "
            f"chords={self.num_chords()})"
        )


# Example usage
if __name__ == "__main__":
    # Create simple C major triad (C-E-G)
    soprano = Voice(
        name="S",
        notes=[Note(midi=72, duration=1.0), Note(midi=74, duration=1.0)]
    )
    alto = Voice(
        name="A",
        notes=[Note(midi=64, duration=1.0), Note(midi=65, duration=1.0)]
    )
    tenor = Voice(
        name="T",
        notes=[Note(midi=60, duration=1.0), Note(midi=62, duration=1.0)]
    )
    bass = Voice(
        name="B",
        notes=[Note(midi=48, duration=1.0), Note(midi=50, duration=1.0)]
    )
    
    score = Score(
        voices={"S": soprano, "A": alto, "T": tenor, "B": bass},
        key="C major",
        meter="4/4"
    )
    
    print(score)
    print(f"Number of chords: {score.num_chords()}")
