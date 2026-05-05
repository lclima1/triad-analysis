import streamlit as st
import pandas as pd
import tempfile
from collections import Counter
from typing import List

from music21 import converter, chord, note, stream


TRIAD_FORMS = {
    "major": {0, 4, 7},
    "minor": {0, 3, 7},
    "diminished": {0, 3, 6},
    "augmented": {0, 4, 8},
}

PC_NAMES = {
    0: "C",
    1: "C♯",
    2: "D",
    3: "E♭",
    4: "E",
    5: "F",
    6: "F♯",
    7: "G",
    8: "A♭",
    9: "A",
    10: "B♭",
    11: "B",
}


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
        return el.tie is not None and el.tie.type in ("stop", "continue")

    return False


def count_noteheads_in_score(s: stream.Stream) -> int:
    total = 0
    for el in s.recurse():
        if isinstance(el, note.Note):
            total += 1
        elif isinstance(el, chord.Chord):
            total += len(el.pitches)
    return total


def classify_exact_triad(pcs_unique: List[int]):
    pcs = set(pcs_unique)

    if len(pcs) != 3:
        return False, None, None

    for root_pc in pcs:
        intervals = {(pc - root_pc) % 12 for pc in pcs}

        for quality, form in TRIAD_FORMS.items():
            if intervals == form:
                return True, quality, root_pc

    return False, None, None


def determine_inversion(quality: str, root_pc: int, bass_pc: int) -> int:
    if bass_pc == root_pc:
        return 0

    if quality == "major":
        if bass_pc == (root_pc + 4) % 12:
            return 1
        if bass_pc == (root_pc + 7) % 12:
            return 2

    if quality == "minor":
        if bass_pc == (root_pc + 3) % 12:
            return 1
        if bass_pc == (root_pc + 7) % 12:
            return 2

    if quality == "diminished":
        if bass_pc == (root_pc + 3) % 12:
            return 1
        if bass_pc == (root_pc + 6) % 12:
            return 2

    if quality == "augmented":
        if bass_pc == (root_pc + 4) % 12:
            return 1
        if bass_pc == (root_pc + 8) % 12:
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

        ch = chord.Chord(pitches)
        pcs_unique = sorted(set(ch.pitchClasses))

        ok, quality, root_pc = classify_exact_triad(pcs_unique)
        if not ok or quality is None or root_pc is None:
            continue

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
            bass_pc = bass.pitchClass if bass else None
            bass_name = pretty_pitch(bass.name) if bass else "?"
            root_name = PC_NAMES.get(root_pc, "?")

            inv = determine_inversion(quality, root_pc, bass_pc) if bass_pc is not None else -1
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
            "pcs": tuple(pcs_unique),
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


st.title("Triad Analyzer (Strict Onset)")

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
