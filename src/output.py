"""
Output pipeline: Export corrected Score to MusicXML, MIDI, LilyPond.

Formats:
  - MusicXML: Standard, editable in MuseScore/Finale/Sibelius
  - MIDI: Playable format
  - LilyPond: Text-based, publication-quality

All use music21 as backend.
"""

from typing import Optional, Dict, Any
from pathlib import Path
import json

from music_model import Score, VOICE_ORDER
from validator import validate
from scoring import compute_score


try:
    from music21 import stream, instrument, tempo, meter, note, environment
    HAS_MUSIC21 = True
except ImportError:
    HAS_MUSIC21 = False
    print("Warning: music21 not installed. Output formats limited to JSON.")


# =========================================================
# Music21 Bridge
# =========================================================

def score_to_music21(score: Score) -> 'stream.Score':
    """
    Convert Scale-Note Score → music21 Score object.
    
    Args:
        score: Scale-Note Score
    
    Returns:
        music21.stream.Score with 4 parts (SATB)
    """
    if not HAS_MUSIC21:
        raise RuntimeError("music21 required for this export format")
    
    # Create top-level score
    s = stream.Score()
    
    # Add metadata
    s.metadata.title = "Generated Composition"
    s.metadata.composer = "Scale-Note AI Pipeline"
    
    # Create 4 parts (S, A, T, B)
    instruments_map = {
        "S": instrument.Soprano(),
        "A": instrument.Alto(),
        "T": instrument.Tenor(),
        "B": instrument.Bass(),
    }
    
    for voice_name in VOICE_ORDER:
        part = stream.Part()
        part.id = voice_name
        part.append(instruments_map[voice_name])
        
        # Add time signature once at start
        if voice_name == "S":
            # Parse meter string "4/4" → numerator, denominator
            meter_parts = score.meter.split("/")
            numerator = int(meter_parts[0])
            denominator = int(meter_parts[1])
            part.append(meter.TimeSignature(f"{numerator}/{denominator}"))
        
        # Add notes
        voice = score.voices[voice_name]
        for note_obj in voice.notes:
            midi = note_obj.midi
            duration = note_obj.duration
            
            # Create music21 note
            n = note.Note(midi=midi)
            n.quarterLength = duration
            part.append(n)
        
        s.append(part)
    
    return s


# =========================================================
# Export to MusicXML
# =========================================================

def export_musicxml(score: Score, path: str, validate_first: bool = True) -> None:
    """
    Export Score to MusicXML (.musicxml).
    
    Args:
        score: Scale-Note Score
        path: Output file path (e.g., "output.musicxml")
        validate_first: Check score validity before export
    """
    if not HAS_MUSIC21:
        raise RuntimeError("music21 required for MusicXML export")
    
    if validate_first:
        errors = validate(score)
        if errors:
            raise ValueError(
                f"Score has {len(errors)} voiceleading errors. "
                "Run correction engine first."
            )
    
    m21_score = score_to_music21(score)
    m21_score.write("musicxml", fp=path)
    print(f"✓ Exported to MusicXML: {path}")


# =========================================================
# Export to MIDI
# =========================================================

def export_midi(score: Score, path: str, tempo_bpm: int = 120, validate_first: bool = True) -> None:
    """
    Export Score to MIDI (.mid).
    
    Args:
        score: Scale-Note Score
        path: Output file path (e.g., "output.mid")
        tempo_bpm: Tempo in beats per minute (default 120)
        validate_first: Check score validity before export
    """
    if not HAS_MUSIC21:
        raise RuntimeError("music21 required for MIDI export")
    
    if validate_first:
        errors = validate(score)
        if errors:
            raise ValueError(
                f"Score has {len(errors)} voiceleading errors. "
                "Run correction engine first."
            )
    
    m21_score = score_to_music21(score)
    
    # Set tempo
    m21_score.insert(0, tempo.MetronomeMarк(number=tempo_bpm))
    
    m21_score.write("midi", fp=path)
    print(f"✓ Exported to MIDI: {path} (tempo={tempo_bpm} BPM)")


# =========================================================
# Export to LilyPond
# =========================================================

def export_lilypond(score: Score, path: str, validate_first: bool = True) -> None:
    """
    Export Score to LilyPond (.ly).
    
    Args:
        score: Scale-Note Score
        path: Output file path (e.g., "output.ly")
        validate_first: Check score validity before export
    """
    if not HAS_MUSIC21:
        raise RuntimeError("music21 required for LilyPond export")
    
    if validate_first:
        errors = validate(score)
        if errors:
            raise ValueError(
                f"Score has {len(errors)} voiceleading errors. "
                "Run correction engine first."
            )
    
    m21_score = score_to_music21(score)
    m21_score.write("lilypond", fp=path)
    print(f"✓ Exported to LilyPond: {path}")


# =========================================================
# Export to JSON (Analysis Format)
# =========================================================

def export_json_analysis(
    score: Score,
    path: str,
    include_analysis: bool = True,
) -> None:
    """
    Export Score to JSON with optional analysis metadata.
    
    Includes:
      - All note pitches and durations
      - Voice ranges
      - Validation errors (if any)
      - Score breakdown (if valid)
    
    Args:
        score: Scale-Note Score
        path: Output file path (e.g., "output.json")
        include_analysis: Include validator + scoring metadata
    """
    data = {
        "metadata": {
            "key": score.key,
            "meter": score.meter,
            "num_chords": score.num_chords(),
        },
        "voices": {},
    }
    
    # Serialize voices
    for voice_name in VOICE_ORDER:
        voice = score.voices[voice_name]
        data["voices"][voice_name] = {
            "notes": [
                {
                    "midi": note_obj.midi,
                    "duration": note_obj.duration,
                }
                for note_obj in voice.notes
            ]
        }
    
    # Add analysis if requested
    if include_analysis:
        errors = validate(score)
        score_result = compute_score(score)
        
        data["analysis"] = {
            "valid": len(errors) == 0,
            "num_errors": len(errors),
            "errors": [
                {
                    "type": e.type,
                    "severity": e.severity,
                    "index": e.index,
                    "voices": e.voices,
                    "description": e.description,
                }
                for e in errors
            ],
            "scoring": {
                "total": score_result.total,
                "error_penalties": score_result.error_penalties,
                "leap_penalties": score_result.leap_penalties,
                "breakdown": score_result.breakdown,
            },
        }
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"✓ Exported to JSON: {path}")


# =========================================================
# Export to Text (Human-Readable)
# =========================================================

def export_text_score(score: Score, path: str) -> None:
    """
    Export Score to plain text (human-readable).
    
    Format:
    ```
    Key: C major | Meter: 4/4 | Chords: 4
    
    Chord 0:
      S: 72 (C6)
      A: 64 (C5)
      T: 60 (C4)
      B: 48 (C3)
    ...
    ```
    
    Args:
        score: Scale-Note Score
        path: Output file path (e.g., "output.txt")
    """
    lines = [
        f"Key: {score.key} | Meter: {score.meter} | Chords: {score.num_chords()}",
        "",
    ]
    
    for chord_idx in range(score.num_chords()):
        lines.append(f"Chord {chord_idx}:")
        for voice_name in VOICE_ORDER:
            note_obj = score.voices[voice_name].notes[chord_idx]
            midi = note_obj.midi
            duration = note_obj.duration
            
            # Convert MIDI to note name (simple)
            midi_to_name = {
                48: "C3", 49: "C#3", 50: "D3", 51: "D#3", 52: "E3", 53: "F3",
                54: "F#3", 55: "G3", 56: "G#3", 57: "A3", 58: "A#3", 59: "B3",
                60: "C4", 61: "C#4", 62: "D4", 63: "D#4", 64: "E4", 65: "F4",
                66: "F#4", 67: "G4", 68: "G#4", 69: "A4", 70: "A#4", 71: "B4",
                72: "C5", 73: "C#5", 74: "D5", 75: "D#5", 76: "E5", 77: "F5",
                78: "F#5", 79: "G5", 80: "G#5", 81: "A5", 82: "A#5", 83: "B5",
            }
            note_name = midi_to_name.get(midi, f"MIDI{midi}")
            
            lines.append(f"  {voice_name}: {midi} ({note_name}) [dur={duration}]")
        
        lines.append("")
    
    # Add analysis
    errors = validate(score)
    score_result = compute_score(score)
    
    lines.append("Analysis:")
    lines.append(f"  Valid: {len(errors) == 0}")
    lines.append(f"  Errors: {len(errors)}")
    lines.append(f"  Score: {score_result.total:.2f}")
    
    if errors:
        lines.append("\n  Voiceleading Issues:")
        for e in errors:
            lines.append(f"    - {e.type} @ {e.index}: {e.description}")
    
    with open(path, "w") as f:
        f.write("\n".join(lines))
    
    print(f"✓ Exported to text: {path}")


# =========================================================
# Multi-Format Export (Convenience)
# =========================================================

def export_all_formats(
    score: Score,
    output_dir: str = "./output",
    basename: str = "composition",
    validate_first: bool = True,
) -> Dict[str, str]:
    """
    Export Score to all available formats.
    
    Args:
        score: Scale-Note Score
        output_dir: Directory for output files
        basename: Base filename (without extension)
        validate_first: Validate score before export
    
    Returns:
        Dict mapping format → file path
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    # Always export text (no dependencies)
    text_path = str(output_path / f"{basename}.txt")
    export_text_score(score, text_path)
    results["text"] = text_path
    
    # Export JSON (no dependencies)
    json_path = str(output_path / f"{basename}.json")
    export_json_analysis(score, json_path, include_analysis=True)
    results["json"] = json_path
    
    # Export music21 formats (if available)
    if HAS_MUSIC21:
        try:
            musicxml_path = str(output_path / f"{basename}.musicxml")
            export_musicxml(score, musicxml_path, validate_first=validate_first)
            results["musicxml"] = musicxml_path
        except Exception as e:
            print(f"✗ MusicXML export failed: {e}")
        
        try:
            midi_path = str(output_path / f"{basename}.mid")
            export_midi(score, midi_path, validate_first=validate_first)
            results["midi"] = midi_path
        except Exception as e:
            print(f"✗ MIDI export failed: {e}")
        
        try:
            lilypond_path = str(output_path / f"{basename}.ly")
            export_lilypond(score, lilypond_path, validate_first=validate_first)
            results["lilypond"] = lilypond_path
        except Exception as e:
            print(f"✗ LilyPond export failed: {e}")
    
    return results


# =========================================================
# Example Usage
# =========================================================

if __name__ == "__main__":
    from realization import realize_progression
    from correction import correct_score
    
    # Generate and correct
    progression = ["C major", "F major", "G7", "C major"]
    rough_score = realize_progression(progression)
    
    print("Generating corrected score...")
    result = correct_score(rough_score, verbose=False)
    corrected_score = result.final_score_result
    
    if not result.success:
        print(f"Warning: Score has residual errors (score={result.final_score:.2f})")
    else:
        print(f"✓ Score valid (score={result.final_score:.2f})")
    
    # Export
    print("\nExporting...")
    exports = export_all_formats(
        corrected_score,
        output_dir="./test_output",
        basename="chorale",
        validate_first=False,
    )
    
    print("\nExported files:")
    for fmt, path in exports.items():
        print(f"  {fmt}: {path}")
