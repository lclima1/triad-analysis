import streamlit as st
import pandas as pd
import tempfile
from collections import Counter
from typing import List

from music21 import converter, chord, note, stream


TRIAD_INTERVALS_BY_LETTER = {
    "major": (4, 7),
    "minor": (3, 7),
    "diminished": (3, 6),
    "augmented": (4, 8),
}

LETTER_ORDER = ["C", "D", "E", "F", "G", "A", "B"]


def pretty_pitch(name: str) -> str:
    return (
        name.replace("##", "𝄪")
        .replace("--", "𝄫")
        .replace("#", "♯")
        .replace("-", "♭")
    )


def is_tied_continuation(el):
    if isinstance(el, note.Note):
        return el.tie is not None and el.tie.type in ("stop", "continue")

    if isinstance(el, chord.Chord):
        try:
            return any(
                n.tie is not None and n.tie.type in ("stop", "continue")
                for n in el.notes
            )
        except Exception:
            return False

    return False


def has_sustained_overlap(flat_score, t: float) -> bool:
    """
    Returns True if any note/chord is already sounding at offset t
    without beginning there, or if a tied continuation begins at t.

    This excludes triadic subsets occurring inside larger sustained sonorities.
    """
    eps = 1e-6

    for el in flat_score.notes:
        if not isinstance(el, (note.Note, chord.Chord)):
            continue

        start = float(el.offset)
        end = start + float(el.quarterLength)

        if start < t < end:
            return True

        if abs(start - t) < eps and is_tied_continuation(el):
            return True

    return False


def count_noteheads_in_score(s: stream.Stream) -> int:
    total = 0
    for el in s.recurse():
        if isinstance(el, note.Note):
            total += 1
        elif isinstance(el, chord.Chord):
            total += len(el.pitches)
    return total


def letter_index(letter: str) -> int:
    return LETTER_ORDER.index(letter)


def pitch_spelling_name(p) -> str:
    """
    Returns pitch spelling without octave, preserving notation:
    C, C♯, C♭, etc.
    """
    return pretty_pitch(p.name)


def pitch_letters_are_root_third_fifth(pitches, root_pitch) -> bool:
    """
    Checks whether the written note letters form root-third-fifth.
    This prevents enharmonic pitch-class sets from being counted
    as triads when the spelling is not tertian.
    """
    root_letter = root_pitch.step
    root_i = letter_index(root_letter)

    expected_letters = {
        LETTER_ORDER[root_i],
        LETTER_ORDER[(root_i + 2) % 7],
        LETTER_ORDER[(root_i + 4) % 7],
    }

    actual_letters = {p.step for p in pitches}

    return actual_letters == expected_letters


def classify_spelled_triad(pitches):
    """
    Strictly classifies only complete tertian triads using both:
    1. written letter spelling: root-third-fifth
    2. semitone intervals: major/minor/diminished/augmented

    This avoids counting non-tertian enharmonic formations as triads.
    """
    unique_spellings = {}

    for p in pitches:
        unique_spellings[p.name] = p

    if len(unique_spellings) != 3:
        return False, None, None

    unique_pitches = list(unique_spellings.values())

    for root_pitch in unique_pitches:
        if not pitch_letters_are_root_third_fifth(unique_pitches, root_pitch):
            continue

        root_pc = root_pitch.pitchClass
        intervals = sorted((p.pitchClass - root_pc) % 12 for p in unique_pitches)

        if intervals == [0, 4, 7]:
            return True, "major", root_pitch

        if intervals == [0, 3, 7]:
            return True, "minor", root_pitch

        if intervals == [0, 3, 6]:
            return True, "diminished", root_pitch

        if intervals == [0, 4, 8]:
            return True, "augmented", root_pitch

    return False, None, None


def determine_inversion_from_spelling(quality: str, root_pitch, bass_pitch) -> int:
    root_letter = root_pitch.step
    bass_letter = bass_pitch.step

    root_i = letter_index(root_letter)

    third_letter = LETTER_ORDER[(root_i + 2) % 7]
    fifth_letter = LETTER_ORDER[(root_i + 4) % 7]

    if bass_letter == root_letter:
        return 0
    if bass_letter == third_letter:
        return 1
    if bass_letter == fifth_letter:
        return 2

    return -1


def analyze_explicit_onsets(score_path: str):
    s = converter.parse(score_path)
    noteheads_total = count_noteheads_in_score(s)
    flat = s.flatten()

    onset_offsets = sorted({
        float(el.offset)
        for el in flat.notes
        if isinstance(el, (note.Note, chord.Chord))
        and not is_tied_continuation(el)
    })

    triad_hits = []
    counts_all = Counter()
    counts_rootpos = Counter()
    onset_event_total = 0

    for t in onset_offsets:
        started_all = flat.getElementsByOffset(
            t,
            mustBeginInSpan=True,
            includeElementsThatEndAtStart=False,
        )

        started = [
            el for el in started_all
            if isinstance(el, (note.Note, chord.Chord))
            and not is_tied_continuation(el)
        ]

        pitches = []

        for el in started:
            if isinstance(el, note.Note):
                pitches.append(el.pitch)
            elif isinstance(el, chord.Chord):
                pitches.extend(list(el.pitches))

        if not pitches:
            continue

        onset_event_total += 1

        # Exclude events where any sustained or tied-over tone is sounding.
        # This prevents counting a triadic subset inside a larger simultaneity.
        if has_sustained_overlap(flat, t):
            continue

        ok, quality, root_pitch = classify_spelled_triad(pitches)
        if not ok or quality is None or root_pitch is None:
            continue

        ch = chord.Chord(pitches)

        ref_el = started[0]
        meas = None
        measure_offset = None

        try:
            mctx = ref_el.getContextByClass(stream.Measure)
            if mctx:
                meas = mctx.number
                measure_offset = round(float(t - mctx.offset), 3)
        except Exception:
            pass

        try:
            bass = ch.bass()
            bass_name = pretty_pitch(bass.name) if bass else "?"
            root_name = pretty_pitch(root_pitch.name)
            inv = determine_inversion_from_spelling(quality, root_pitch, bass) if bass else -1
        except Exception:
            inv = -1
            root_name = "?"
            bass_name = "?"

        pitches_str = " ".join(
            pretty_pitch(p.nameWithOctave) for p in sorted(ch.pitches)
        )

        triad_hits.append({
            "measure": meas,
            "measure_offset_qn": measure_offset,
            "quality": quality,
            "inversion": inv,
            "root": root_name,
            "bass": bass_name,
            "pitches": pitches_str,
            "spellings": tuple(sorted(pitch_spelling_name(p) for p in pitches)),
        })

        counts_all[quality] += 1
        if inv == 0:
            counts_rootpos[quality] += 1

    triad_total = len(triad_hits)
    rootpos_total = sum(counts_rootpos.values())

    triads_per_100_notes = (triad_total / noteheads_total * 100) if noteheads_total else 0
    rootpos_per_100_notes = (rootpos_total / noteheads_total * 100) if noteheads_total else 0
    triad_event_share = (triad_total / onset_event_total * 100) if onset_event_total else 0

    summary = {
        "Total triads": triad_total,
        "Triad-event share (%)": round(triad_event_share, 2),
        "Triads per 100 notes": round(triads_per_100_notes, 2),
        "Root-position per 100 notes": round(rootpos_per_100_notes, 2),
        "Onset events": onset_event_total,
        "Noteheads": noteheads_total,
    }

    return triad_hits, summary


st.title("Triad Analysis")

uploaded_file = st.file_uploader(
    "Upload MusicXML (.mxl or .xml)",
    type=["mxl", "xml", "musicxml"],
)

if uploaded_file:
    suffix = ".mxl" if uploaded_file.name.endswith(".mxl") else ".musicxml"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        path = tmp.name

    hits, summary = analyze_explicit_onsets(path)

    st.subheader("Summary")
    st.write(summary)

    df = pd.DataFrame(hits)
    st.subheader("Detected Triads")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, "triads.csv", "text/csv")
