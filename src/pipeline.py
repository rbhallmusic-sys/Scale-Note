"""
Main orchestration pipeline: End-to-end composition generation.

Flow:
  1. Input: Chord progression
  2. Realization (Phase 4): Generate rough SATB
  3. Validation (Phase 1): Check for errors
  4. Correction (Phase 5): Fix errors with greedy search
  5. Output (Phase 6): Export to multiple formats
"""

from typing import List, Optional, Dict
from pathlib import Path

from realization import realize_progression
from validator import validate
from scoring import compute_score
from correction import correct_score, CorrectionResult
from output import export_all_formats
from music_model import Score


def compose(
    chord_progression: List[str],
    key: str = "C major",
    meter: str = "4/4",
    duration: float = 1.0,
    max_correction_iterations: int = 1000,
    verbose: bool = False,
) -> Dict[str, object]:
    """
    Complete composition pipeline: chords → corrected SATB score.
    
    Args:
        chord_progression: List of chord symbols (e.g., ["C major", "F major", "G7"])
        key: Key signature (for context)
        meter: Time signature (e.g., "4/4")
        duration: Note duration in quarter notes
        max_correction_iterations: Max greedy correction steps
        verbose: Print progress
    
    Returns:
        Dict with:
          - "score": Final corrected Score object
          - "initial_errors": List of errors before correction
          - "correction_result": CorrectionResult from Phase 5
          - "success": Boolean (valid score?)
    """
    
    if verbose:
        print(f"Scale-Note Pipeline")
        print(f"  Chords: {chord_progression}")
        print(f"  Key: {key}, Meter: {meter}")
        print()
    
    # ===== Phase 4: Realization =====
    if verbose:
        print("[1/3] Realization Engine")
    
    rough_score = realize_progression(
        chord_progression,
        key=key,
        meter=meter,
        duration=duration,
    )
    
    if verbose:
        print(f"  Generated {rough_score.num_chords()} chords")
    
    # ===== Phase 1: Validation =====
    if verbose:
        print("[2/3] Validation")
    
    initial_errors = validate(rough_score)
    
    if verbose:
        if initial_errors:
            print(f"  Found {len(initial_errors)} errors:")
            error_types = {}
            for e in initial_errors:
                error_types[e.type] = error_types.get(e.type, 0) + 1
            for etype, count in error_types.items():
                print(f"    - {etype}: {count}")
        else:
            print(f"  ✓ No errors found!")
    
    # ===== Phase 5: Correction =====
    if verbose:
        print("[3/3] Correction Engine")
    
    correction_result = correct_score(
        rough_score,
        max_iterations=max_correction_iterations,
        verbose=verbose,
    )
    
    if verbose:
        if correction_result.success:
            print(f"  ✓ Converged to valid score")
        else:
            print(f"  ✗ Max iterations reached (residual errors)")
        print(f"  Iterations: {correction_result.iterations}")
        print(f"  Score: {correction_result.initial_score:.2f} → {correction_result.final_score:.2f}")
    
    return {
        "score": correction_result.final_score_result,
        "initial_errors": initial_errors,
        "correction_result": correction_result,
        "success": correction_result.success,
    }


def compose_and_export(
    chord_progression: List[str],
    output_dir: str = "./output",
    basename: str = "composition",
    key: str = "C major",
    meter: str = "4/4",
    duration: float = 1.0,
    max_correction_iterations: int = 1000,
    verbose: bool = True,
) -> Dict[str, str]:
    """
    End-to-end: Generate composition and export to all formats.
    
    Args:
        chord_progression: List of chord symbols
        output_dir: Directory for output files
        basename: Base filename (without extension)
        key: Key signature
        meter: Time signature
        duration: Note duration
        max_correction_iterations: Max correction steps
        verbose: Print progress
    
    Returns:
        Dict mapping format → file path
    
    Example:
        >>> exports = compose_and_export(
        ...     ["C major", "F major", "G7", "C major"],
        ...     output_dir="./output",
        ...     verbose=True
        ... )
        >>> print(exports["musicxml"])
        './output/composition.musicxml'
    """
    
    if verbose:
        print("=" * 60)
        print("SCALE-NOTE: AI-Assisted Music Composition Pipeline")
        print("=" * 60)
        print()
    
    # ===== Composition =====
    result = compose(
        chord_progression,
        key=key,
        meter=meter,
        duration=duration,
        max_correction_iterations=max_correction_iterations,
        verbose=verbose,
    )
    
    score = result["score"]
    
    if verbose:
        print()
        print("=" * 60)
        print("EXPORT")
        print("=" * 60)
        print()
    
    # ===== Output (Phase 6) =====
    exports = export_all_formats(
        score,
        output_dir=output_dir,
        basename=basename,
        validate_first=False,  # We know it's valid from correction
    )
    
    if verbose:
        print()
        print("=" * 60)
        print("COMPLETE")
        print("=" * 60)
        print(f"Status: {'✓ SUCCESS' if result['success'] else '✗ PARTIAL'}")
        print(f"Output Directory: {output_dir}")
        print()
    
    return exports


# =========================================================
# Example Usage
# =========================================================

if __name__ == "__main__":
    # Example: Simple I-IV-V-I progression in C major
    progression = [
        "C major",
        "F major",
        "G major",
        "C major",
    ]
    
    # Option 1: Just compose (no export)
    print("\n=== Option 1: Composition Only ===\n")
    result = compose(progression, verbose=True)
    print(f"\nFinal score: {result['correction_result'].final_score:.2f}")
    print(f"Success: {result['success']}")
    
    # Option 2: Compose and export (all formats)
    print("\n\n=== Option 2: Compose + Export ===\n")
    exports = compose_and_export(
        progression,
        output_dir="./test_output",
        basename="my_chorale",
        verbose=True,
    )
