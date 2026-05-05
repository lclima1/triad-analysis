# Triad Analyzer

This tool performs a computational analysis of triadic structures in MusicXML scores based on explicit simultaneity.

Rather than inferring harmonic function, the analysis focuses exclusively on noteheads that begin at the same time. Sustained tones, tied continuations, and implied harmonies are excluded. This allows for a reproducible and clearly defined measurement of triadic presence within the musical surface.

## Method

An onset event is defined as a set of noteheads that begin at the same global position in the score. Only these explicitly articulated vertical sonorities are considered.

A triad is identified when:
- exactly three unique pitch classes are present
- the interval structure corresponds to a major, minor, diminished, or augmented triad

Triads are classified by:
- quality (major, minor, diminished, augmented)
- inversion (root position, first inversion, second inversion)

## Output

The tool provides:

- Total number of triads
- Triad-event share (% of onset events)
- Triads per 100 noteheads
- Root-position triads per 100 noteheads
- Event-level data including:
  - measure
  - position within the measure (in quarter-note units)
  - pitch content
  - inversion
  - root and bass

## Interface

The application is built with Streamlit and allows users to upload MusicXML (`.mxl`, `.xml`, `.musicxml`) files directly in the browser.

## Purpose

This tool was developed as part of a research project on the changing role of the triad in early twentieth-century music.

By reducing harmonic analysis to explicitly observable simultaneities, the method provides a quantitative perspective on structural transformations without relying on functional or perceptual interpretation.

## Technologies

- Python
- music21
- Streamlit
- pandas

