"""
Correction engine: Local search + greedy optimization.

Strategy:
  1. Detect highest-severity error from validator
  2. Generate candidate fixes (note mutations)
  3. Rescore all candidates
  4. Accept best improvement
  5. Repeat until score == 0 (valid) or max iterations reached

This is the core innovation: search-based voiceleading correction.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Set
from copy import deepcopy

from music_model import Score, Voice, Note, VOICE_RANGES, VOICE_ORDER
from validator import ValidationError, validate
from scoring import compute_score, ScoreResult
from pitch_utils import semitones_between


# =========================================================
# Configuration
# =========================================================

MAX_ITERATIONS = 1000
CONVERGENCE_TOLERANCE = 0.01  # Stop if improvement < this
CANDIDATE_DEPTH = 3  # How many note options to try per position


@dataclass
class CorrectionStep:
    """Record of one correction iteration."""
    iteration: int
    error: Optional[ValidationError]
    voice: str
    chord_idx: int
    old_midi: int
    new_midi: int
    old_score: float
    new_score: float
    improvement: float


@dataclass
class CorrectionResult:
    """Output of full correction process."""
    success: bool
    initial_score: float
    final_score: float
    iterations: int
    steps: List[CorrectionStep]
    final_score_result: ScoreResult


# =========================================================
# Candidate Generation
# =========================================================

def generate_note_candidates(
    midi: int,
    voice_name: str,
    chord_pitches: Set[int],
    depth: int = CANDIDATE_DEPTH,
) -> List[int]:
    """
    Generate alternative MIDI pitches for a voice.
    
    Candidates:
      - Original pitch
      - ±1, ±2 semitones (chromatic neighbors)
      - Other chord tones (within voice range)
    
    Args:
        midi: Current MIDI pitch
        voice_name: "S", "A", "T", "B"
        chord_pitches: Set of valid chord tones for this chord
        depth: How far to search (semitones)
    
    Returns:
        Sorted list of candidate MIDI pitches
    """
    low, high = VOICE_RANGES[voice_name]
    candidates = set()
    
    # Add original
    candidates.add(midi)
    
    # Add chromatic neighbors within depth
    for offset in range(-depth, depth + 1):
        candidate = midi + offset
        if low <= candidate <= high:
            candidates.add(candidate)
    
    # Add chord tones (within range)
    for pitch in chord_pitches:
        # Try pitch in multiple octaves
        for octave_offset in [-1, 0, 1]:
            candidate = pitch + (octave_offset * 12)
            if low <= candidate <= high:
                candidates.add(candidate)
    
    return sorted(list(candidates))


def get_chord_pitches_at_index(score: Score, chord_idx: int) -> Set[int]:
    """Extract all pitches in a chord (for candidate generation)."""
    pitches = set()
    for voice_name in VOICE_ORDER:
        pitches.add(score.voices[voice_name].notes[chord_idx].midi)
    return pitches


# =========================================================
# Single Note Mutation
# =========================================================

def mutate_note(score: Score, voice_name: str, chord_idx: int, new_midi: int) -> Score:
    """
    Create new Score with one note changed.
    
    Args:
        score: Original score
        voice_name: Voice to mutate ("S", "A", "T", "B")
        chord_idx: Chord index to modify
        new_midi: New MIDI pitch
    
    Returns:
        New Score object (original unchanged)
    """
    new_score = deepcopy(score)
    new_score.voices[voice_name].notes[chord_idx].midi = new_midi
    return new_score


# =========================================================
# Error Selection & Targeting
# =========================================================

def select_target_error(errors: List[ValidationError]) -> Optional[ValidationError]:
    """
    Select which error to fix next (greedy priority).
    
    Priority:
      1. Parallel fifths/octaves (highest severity)
      2. Voice crossing
      3. Range violations
      4. Spacing warnings
    
    Within same severity: earliest chord first
    """
    if not errors:
        return None
    
    # Sort by severity + index
    severity_rank = {
        "parallel_fifth": 0,
        "parallel_octave": 0,
        "voice_crossing": 1,
        "range_violation": 2,
        "spacing_violation": 3,
    }
    
    ranked = sorted(
        errors,
        key=lambda e: (severity_rank.get(e.type, 999), e.index)
    )
    
    return ranked[0]


def get_voices_to_try(error: ValidationError) -> List[str]:
    """
    Determine which voices to mutate to fix this error.
    
    Strategy:
      - If error involves specific voices, try those first
      - Generally try inner voices before outer
    """
    involved = set(error.voices)
    
    # Try inner voices first (more flexible)
    priority = ["A", "T", "S", "B"]
    result = [v for v in priority if v in involved]
    
    # If no specific voices involved, try all
    if not result:
        result = priority
    
    return result


# =========================================================
# Greedy Correction Loop
# =========================================================

def correct_score(
    score: Score,
    max_iterations: int = MAX_ITERATIONS,
    convergence_tol: float = CONVERGENCE_TOLERANCE,
    verbose: bool = False,
) -> CorrectionResult:
    """
    Greedily correct voiceleading errors in a score.
    
    Algorithm:
      1. Validate score, get errors
      2. Select highest-priority error
      3. For each involved voice:
         - Generate note candidates
         - Rescore each candidate
         - Keep best (lowest score)
      4. If improved, accept mutation + repeat
      5. If no improvement, try next error
      6. Repeat until valid or max_iterations
    
    Args:
        score: Initial (rough) Score
        max_iterations: Max correction steps before stopping
        convergence_tol: Stop if improvement < this
        verbose: Print progress
    
    Returns:
        CorrectionResult with final score + history
    """
    
    current_score = deepcopy(score)
    initial_result = compute_score(current_score)
    initial_score_value = initial_result.total
    
    steps = []
    iteration = 0
    
    if verbose:
        print(f"Starting correction: score={initial_score_value:.2f}")
    
    while iteration < max_iterations:
        # Check validity
        errors = validate(current_score)
        current_result = compute_score(current_score)
        current_score_value = current_result.total
        
        if current_result.error_penalties == 0.0:
            if verbose:
                print(f"✓ Converged to valid score in {iteration} iterations")
            break
        
        # Select error to fix
        target_error = select_target_error(errors)
        if not target_error:
            break
        
        # Try fixing with different voices
        best_candidate_score = current_score_value
        best_mutation = None
        best_voice = None
        best_new_midi = None
        
        voices_to_try = get_voices_to_try(target_error)
        chord_idx = target_error.index
        chord_pitches = get_chord_pitches_at_index(current_score, chord_idx)
        
        for voice_name in voices_to_try:
            current_midi = current_score.voices[voice_name].notes[chord_idx].midi
            
            # Generate candidates
            candidates = generate_note_candidates(
                current_midi,
                voice_name,
                chord_pitches,
                depth=CANDIDATE_DEPTH,
            )
            
            # Score each candidate
            for candidate_midi in candidates:
                mutated = mutate_note(current_score, voice_name, chord_idx, candidate_midi)
                mutated_result = compute_score(mutated)
                mutated_score_value = mutated_result.total
                
                # Keep best
                if mutated_score_value < best_candidate_score:
                    best_candidate_score = mutated_score_value
                    best_mutation = mutated
                    best_voice = voice_name
                    best_new_midi = candidate_midi
        
        # Check for improvement
        improvement = current_score_value - best_candidate_score
        
        if improvement > convergence_tol and best_mutation is not None:
            # Accept mutation
            old_midi = current_score.voices[best_voice].notes[chord_idx].midi
            current_score = best_mutation
            
            step = CorrectionStep(
                iteration=iteration,
                error=target_error,
                voice=best_voice,
                chord_idx=chord_idx,
                old_midi=old_midi,
                new_midi=best_new_midi,
                old_score=current_score_value,
                new_score=best_candidate_score,
                improvement=improvement,
            )
            steps.append(step)
            
            if verbose:
                print(
                    f"  [{iteration}] {target_error.type} @ {chord_idx}: "
                    f"{best_voice} {old_midi}→{best_new_midi} "
                    f"score {current_score_value:.2f}→{best_candidate_score:.2f}"
                )
        else:
            # No improvement on this error - skip to next
            if verbose:
                print(f"  [{iteration}] {target_error.type} @ {chord_idx}: no improvement, skipping")
        
        iteration += 1
    
    # Final score
    final_result = compute_score(current_score)
    
    return CorrectionResult(
        success=final_result.error_penalties == 0.0,
        initial_score=initial_score_value,
        final_score=final_result.total,
        iterations=iteration,
        steps=steps,
        final_score_result=final_result,
    )


# =========================================================
# Result Utilities
# =========================================================

def correction_summary(result: CorrectionResult) -> str:
    """Pretty-print correction result."""
    lines = [
        f"Correction Summary",
        f"  Success: {result.success}",
        f"  Initial score: {result.initial_score:.2f}",
        f"  Final score:   {result.final_score:.2f}",
        f"  Improvement:   {result.initial_score - result.final_score:.2f}",
        f"  Iterations:    {result.iterations}",
        f"  Steps taken:   {len(result.steps)}",
    ]
    
    if result.steps:
        lines.append("\n  Correction steps:")
        for step in result.steps:
            lines.append(
                f"    [{step.iteration}] {step.error.type} @ chord {step.chord_idx}: "
                f"{step.voice} {step.old_midi}→{step.new_midi} "
                f"({step.old_score:.2f}→{step.new_score:.2f})"
            )
    
    return "\n".join(lines)


# =========================================================
# Example Usage
# =========================================================

if __name__ == "__main__":
    from realization import realize_progression
    
    # Generate rough score
    progression = ["C major", "F major", "G7", "C major"]
    rough_score = realize_progression(progression)
    
    print("Before correction:")
    print(f"  Score: {compute_score(rough_score).total:.2f}")
    errors = validate(rough_score)
    print(f"  Errors: {len(errors)}")
    for e in errors[:3]:
        print(f"    - {e.type} @ {e.index}: {e.description}")
    
    # Correct
    print("\nCorrecting...")
    result = correct_score(rough_score, verbose=True)
    
    print("\n" + correction_summary(result))
    
    if result.success:
        print("\n✓ Score is now valid!")
