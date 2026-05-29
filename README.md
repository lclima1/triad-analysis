# Triad Analysis

This tool performs a computational analysis of triadic structures in MusicXML scores based on explicit onset simultaneity.

Rather than inferring harmonic function, the analysis focuses exclusively on pitches that begin at the same onset. Pitches sustained from previous events through ties or duration overlap are excluded from the triadic evaluation. This allows for a reproducible and clearly defined measurement of explicitly articulated triadic formations within the musical texture.

## Method

An onset event is defined as the collection of noteheads that begin at the same global position in the score. Only pitches explicitly articulated at that onset are considered.

A triad is identified when:
- exactly three uniquely spelled pitches are present
- the pitch spelling forms a properly tertian major, minor, diminished, or augmented triad

Triads are classified by:
- quality (major, minor, diminished, augmented)
- inversion (root position, first inversion, second inversion)

## Output

The tool provides:

- Total number of triads
- Triad-event share (% of onset events)
- Triads (% of noteheads)
- Root-position triads (% of noteheads)
- Event-level data including:
  - measure
  - position within the measure
  - pitch content
  - inversion
  - root and bass

## Interface

The application is built with Streamlit and allows users to upload MusicXML (.mxl, .xml, .musicxml) files directly in the browser.

## Purpose

This tool was developed as part of a research project on the changing role of explicitly articulated triadic formations in early twentieth-century music.

By reducing harmonic analysis to onset-defined simultaneities, the method provides a quantitative perspective on structural transformations without relying on functional, perceptual, or voice-leading interpretation. The procedure does not attempt to reconstruct complete sounding sonorities, latent harmonic relations, or implied tonal functions; it measures only triadic structures that are explicitly presented as onset events in the score.

## Technologies

- Python
- music21
- Streamlit
- pandas
