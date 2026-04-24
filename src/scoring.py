"""
Scoring system for music quality assessment.

Converts ValidationErrors → numerical penalties.
Scoring is deterministic, reproducible, and tunable.

score = base + parallel_penalties + range_penalties + 
         spacing_penalties + voice_independence_penalties

Lower score = better (penalties are positive).
"""

from dataclasses import dataclass
from typing import List, Dict

from music_model import Score, Note
from validator import ValidationError, validate
from pitch_utils import semitones_between, is_perfect_fifth, is_octave


# =========================================================
# Scoring Constants (TUNABLE WEIGHTS)
# =========================================================

# Hard error penalties (critical violations)
PENALTY_PARALLEL_FIFTH = 1000.0
PENALTY_PARALLEL_OCTAVE = 1000.0
PENALTY_RANGE_VIOLATION = 500.0
PENALTY_VOICE_CROSSING = 800.0

# Soft constraint penalties (warnings/style)
PENALTY_SPACING_VIOLATION = 50.0  # Per semitone over limit

# Soft style penalties (quality of voicing)
PENALTY_LARGE_LEAP = 5.0  # Per semitone over P4 (5 semitones)
PENALTY_NON_STEPWISE = 1.0  # Per semitone of motion

# Voice independence (penalize parallel motion even if not P5/P8)
PENALTY_PARALLEL_MOTION_SIMILAR = 10.0  # Slight penalty for similar motion

# Base score (perfect voicing)
BASE_SCORE = 0.0


# =========================================================
# Error-to-Penalty Mapping
# =========================================================

def penalty_for_error(error: ValidationError) -> float:
    """Convert a ValidationError to a penalty score."""
    
    if error.type == "parallel_fifth":
        return PENALTY_PARALLEL_FIFTH
    
    elif error.type == "parallel_octave":
        return PENALTY_PARALLEL_OCTAVE
    
    elif error.type == "range_violation":
        return PENALTY_RANGE_VIOLATION
    
    elif error.type == "voice_crossing":
        return PENALTY_VOICE_CROSSING
    
    elif error.type == "spacing_violation":
        # Penalties scale with severity
        if "too wide" in error.description:
            # Extract semitones from description
            try:
                parts = error.description.split(":")
                semitones_str = parts[-1].strip().split()[0]
                semitones = float(semitones_str)
                # Penalize each semitone over 12
                excess = max(0, semitones - 12)
                return excess * PENALTY_SPACING_VIOLATION
            except:
                return PENALTY_SPACING_VIOLATION
        return PENALTY_SPACING_VIOLATION
    
    else:
        # Unknown error type - default penalty
        return 100.0


# =========================================================
# Soft Constraint Scoring
# =========================================================

def score_leap_penalty(score: Score) -> float:
    """
    Penalize large leaps (intervals > perfect 4th = 5 semitones).
    Preference for stepwise motion in all voices.
    """
    penalty = 0.0
    
    for voice_name, voice in score.voices.items():
        for i in range(len(voice.notes) - 1):
            midi1 = voice.notes[i].midi
            midi2 = voice.notes[i + 1].midi
            
            interval = abs(semitones_between(midi1, midi2))
            
            # Penalize if > P4 (5 semitones)
            if interval > 5:
                excess = interval - 5
                penalty += excess * PENALTY_LARGE_LEAP
    
    return penalty


def score_parallel_similar_motion(score: Score) -> float:
    """
    Mild penalty for similar motion between voices (voice independence).
    This is a soft constraint - not an error, but discouraged.
    """
    penalty = 0.0
    
    voices = score.voices
    voice_names = ["S", "A", "T", "B"]
    
    for i in range(len(voice_names)):
        for j in range(i + 1, len(voice_names)):
            v1_name = voice_names[i]
            v2_name = voice_names[j]
            
            v1_notes = voices[v1_name].notes
            v2_notes = voices[v2_name].notes
            
            for k in range(len(v1_notes) - 1):
                m1_a = v1_notes[k].midi
                m1_b = v2_notes[k].midi
                m2_a = v1_notes[k + 1].midi
                m2_b = v2_notes[k + 1].midi
                
                # Both voices move in same direction
                dir1 = (m2_a - m1_a) > 0
                dir2 = (m2_b - m1_b) > 0
                
                if dir1 == dir2 and m2_a != m1_a and m2_b != m1_b:
                    # Similar motion - slight penalty
                    penalty += PENALTY_PARALLEL_MOTION_SIMILAR
    
    return penalty


# =========================================================
# Combined Scoring Function
# =========================================================

@dataclass
class ScoreResult:
    """Breakdown of score components."""
    total: float
    error_penalties: float
    leap_penalties: float
    similarity_penalties: float
    breakdown: Dict[str, float]


def compute_score(score: Score, include_soft: bool = True) -> ScoreResult:
    """
    Compute total quality score for a Score object.
    
    Args:
        score: The Score to evaluate
        include_soft: If True, include soft constraint penalties
                     If False, only hard errors
    
    Returns:
        ScoreResult with total and component breakdown
    """
    
    breakdown = {}
    
    # 1. Hard errors (validation)
    errors = validate(score)
    error_penalty = 0.0
    error_counts = {}
    
    for error in errors:
        penalty = penalty_for_error(error)
        error_penalty += penalty
        
        error_type = error.type
        error_counts[error_type] = error_counts.get(error_type, 0) + 1
        breakdown[f"error_{error_type}"] = breakdown.get(f"error_{error_type}", 0) + penalty
    
    # 2. Soft penalties (if enabled)
    leap_penalty = 0.0
    similarity_penalty = 0.0
    
    if include_soft:
        leap_penalty = score_leap_penalty(score)
        similarity_penalty = score_parallel_similar_motion(score)
        
        breakdown["leap_penalty"] = leap_penalty
        breakdown["similarity_penalty"] = similarity_penalty
    
    total = BASE_SCORE + error_penalty + leap_penalty + similarity_penalty
    
    return ScoreResult(
        total=total,
        error_penalties=error_penalty,
        leap_penalties=leap_penalty,
        breakdown=breakdown,
    )


# =========================================================
# Scoring Utilities
# =========================================================

def is_valid(score: Score) -> bool:
    """Check if score has zero hard errors (error_penalties == 0)."""
    result = compute_score(score, include_soft=False)
    return result.error_penalties == 0.0


def score_string(result: ScoreResult) -> str:
    """Pretty-print score breakdown."""
    lines = [
        f"Total Score: {result.total:.2f}",
        f"  Error Penalties:      {result.error_penalties:.2f}",
        f"  Leap Penalties:       {result.leap_penalties:.2f}",
        f"  Breakdown:",
    ]
    
    for key, value in sorted(result.breakdown.items()):
        if value > 0:
            lines.append(f"    {key}: {value:.2f}")
    
    return "\n".join(lines)


# =========================================================
# Example Usage
# =========================================================

if __name__ == "__main__":
    from music_model import Voice, Note
    
    # Create a simple score (will have errors)
    soprano = Voice(
        name="S",
        notes=[Note(midi=72), Note(midi=74)]
    )
    alto = Voice(
        name="A",
        notes=[Note(midi=64), Note(midi=65)]
    )
    tenor = Voice(
        name="T",
        notes=[Note(midi=60), Note(midi=62)]
    )
    bass = Voice(
        name="B",
        notes=[Note(midi=48), Note(midi=50)]
    )
    
    test_score = Score(
        voices={"S": soprano, "A": alto, "T": tenor, "B": bass},
        key="C major",
        meter="4/4"
    )
    
    result = compute_score(test_score)
    print(score_string(result))
    print(f"\nIs valid? {is_valid(test_score)}")
