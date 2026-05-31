import streamlit as st
import pandas as pd
import tempfile
from collections import Counter

from music21 import converter, chord, note, stream, meter


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


def human_measure_position(offset, time_signature=None):
    if offset is None:
        return "?"

    offset = round(float(offset), 3)

    if time_signature is not None:
        beat_length = float(time_signature.beatDuration.quarterLength)
    else:
        beat_length = 1.0

    beat_number = int(offset // beat_length) + 1
    remainder = round(offset - ((beat_number - 1) * beat_length), 3)

    if remainder == 0:
        return f"beat {beat_number}"
    if remainder == 0.25:
        return f"beat {beat_number} + sixteenth"
    if remainder == 0.5:
        return f"beat {beat_number} + eighth"
    if remainder == 0.75:
        return f"beat {beat_number} + dotted eighth"
    if remainder == 1.0:
        return f"beat {beat_number} + quarter"
    if remainder == 1.5:
        return f"beat {beat_number} + dotted quarter"

    return f"beat {beat_number} + {remainder} quarter notes"


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
    return pretty_pitch(p.name)


def pitch_letters_are_root_third_fifth(pitches, root_pitch) -> bool:
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


def determine_inversion_from_spelling(root_pitch, bass_pitch) -> int:
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

        ok, quality, root_pitch = classify_spelled_triad(pitches)

        if not ok or quality is None or root_pitch is None:
            continue

        ch = chord.Chord(pitches)

        ref_el = started[0]
        meas = None
        position = "?"

        try:
            mctx = ref_el.getContextByClass(stream.Measure)

            if mctx:
                meas = mctx.number
                measure_offset = round(float(t - mctx.offset), 3)
                ts = mctx.getContextByClass(meter.TimeSignature)
                position = human_measure_position(measure_offset, ts)

        except Exception:
            pass

        try:
            bass = ch.bass()
            bass_name = pretty_pitch(bass.name) if bass else "?"
            root_name = pretty_pitch(root_pitch.name)
            inv = determine_inversion_from_spelling(root_pitch, bass) if bass else -1

        except Exception:
            inv = -1
            root_name = "?"
            bass_name = "?"

        pitches_str = " ".join(
            pretty_pitch(p.nameWithOctave) for p in sorted(ch.pitches)
        )

        triad_hits.append({
            "measure": meas,
            "position": position,
            "quality": quality,
            "inversion": inv,
            "root": root_name,
            "bass": bass_name,
            "pitches": pitches_str,
            "spellings": tuple(sorted(pitch_spelling_name(p) for p in pitches)),
        })

        if inv == 0:
            counts_rootpos[quality] += 1

    triad_total = len(triad_hits)
    rootpos_total = sum(counts_rootpos.values())

    triads_percent_noteheads = (
        triad_total / noteheads_total * 100
    ) if noteheads_total else 0

    rootpos_percent_noteheads = (
        rootpos_total / noteheads_total * 100
    ) if noteheads_total else 0

    triad_event_share = (
        triad_total / onset_event_total * 100
    ) if onset_event_total else 0

    summary = {
        "Total triads": triad_total,
        "Triad-event share (%)": round(triad_event_share, 2),
        "Triads (% of noteheads)": round(triads_percent_noteheads, 2),
        "Root-position triads (% of noteheads)": round(rootpos_percent_noteheads, 2),
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

    desired_columns = [
        "measure",
        "position",
        "quality",
        "inversion",
        "root",
        "bass",
        "pitches",
        "spellings",
    ]

    df = df[[col for col in desired_columns if col in df.columns]]

    st.subheader("Detected Triads")
    st.dataframe(df, use_container_width=True)

    summary_df = pd.DataFrame(
        list(summary.items()),
        columns=["metric", "value"]
    )

    combined_csv = (
        "Summary\n"
        + summary_df.to_csv(index=False)
        + "\nDetected Triads\n"
        + df.to_csv(index=False)
    ).encode("utf-8")

        original_name = uploaded_file.name.rsplit(".", 1)[0]
    download_name = f"{original_name}_triad_analysis.csv"

    st.download_button(
        "Download triad analysis",
        combined_csv,
        download_name,
        "text/csv",
    )
