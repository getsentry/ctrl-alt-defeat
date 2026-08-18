#!/usr/bin/env python3
"""Synthesise the round result stings.

The game has no audio assets and no sound designer, so the two stings the
round result screen plays are generated here rather than shipped as opaque
files. Run this to regenerate them after changing anything below:

    python tools/create_sounds.py

It writes two pairs. The game loads the first:

    round_won.wav / round_lost.wav        the synth pair, in use
    round_won_chime.wav / _lost_chime.wav the plainer pair, kept as a fallback

To go back to the fallback, point the two preloads at the top of
`client/scripts/round_result_overlay.gd` at the `_chime` files.

Both pairs are the same shape: a phrase that resolves into a chord, then a tail
that fades over a couple of seconds. A win rises into a major chord, a loss
falls into a minor one.

Every voice is a stack of sine harmonics rather than a raw saw or square. A saw
is the obvious way to make a sound synthetic and it is also why a sting ends up
abrasive: its harmonics run all the way to Nyquist, so every repeat scrapes and
anything above the top note aliases. Stacking a fixed number of harmonics gives
the same shape with a ceiling on it.

What separates the synth pair from the chime pair is not the notes but the
filter. A resonant low-pass that opens as the win arrives, and closes as the
loss dies, is the sound of a synthesiser being played rather than a chord being
struck - and it is the one ingredient that reads as cyberpunk rather than as
orchestral. The echoes behind it, spaced off a dotted beat, do the rest.
"""

import math
import struct
import wave
from pathlib import Path

RATE = 44100
OUT = Path(__file__).resolve().parent.parent / "client" / "assets" / "audio"

# Peak level of the written file. These play over a battle the player is still
# looking at, so they sit under it rather than on top of it.
PEAK = 0.55

# Below this the note has faded past hearing and is not worth the arithmetic.
SILENT = 0.0015


def voice(buffer, start, freq, gain, attack, decay, length=None, harmonics=5,
          detune=0.0, voices=1, rolloff=1.7, glide=1.0):
    """Add one note, built from a stack of sine harmonics.

    `rolloff` sets how fast the harmonics fall away: lower is brighter and more
    saw-like, higher is warmer. `voices` and `detune` stack copies spread a
    fraction apart, which is what makes one note sound like a bank of
    oscillators instead of a tuning fork. `glide` bends the pitch by that
    factor across the note.
    """
    first = int(start * RATE)
    count = len(buffer) - first
    if length is not None:
        count = min(count, int(length * RATE))
    if count <= 0:
        return

    if voices > 1:
        # Spread the copies either side of the true pitch, so the note itself
        # stays in tune however many there are.
        spread = [1.0 + detune * (i / (voices - 1.0) - 0.5) * 2.0 for i in range(voices)]
    else:
        spread = [1.0]

    weight = sum(1.0 / (n + 1) ** rolloff for n in range(harmonics))
    level = gain / (len(spread) * weight)
    for copy in spread:
        phases = [0.0] * harmonics
        for i in range(count):
            t = i / RATE
            envelope = math.exp(-t / decay) * min(1.0, t / attack)
            # Only give up once the attack is over, or every note stops on its
            # own first sample, where the envelope is still zero.
            if t > attack and envelope < SILENT:
                break
            bend = glide ** (i / count)
            step = 2.0 * math.pi * freq * copy * bend / RATE
            value = 0.0
            for n in range(harmonics):
                phases[n] += step * (n + 1)
                value += math.sin(phases[n]) / (n + 1) ** rolloff
            buffer[first + i] += value * envelope * level


def sweep_filter(buffer, from_hz, to_hz, resonance=1.0, over=1.0, curve=1.0):
    """A resonant low-pass whose cutoff travels from `from_hz` to `to_hz`.

    This is the part that sounds like a synthesiser. Opening it as a chord
    arrives makes the chord bloom; closing it as one dies makes the sound run
    down rather than simply stop.

    A Chamberlin state variable filter: cheap, and stable as long as the
    damping stays above the tuning coefficient, which is what the clamps below
    are for.
    """
    low = 0.0
    band = 0.0
    damping = max(1.0 / max(resonance, 0.05), 0.75)
    span = max(over * RATE, 1.0)
    for i, sample in enumerate(buffer):
        travelled = min(1.0, i / span) ** curve
        cutoff = from_hz * (to_hz / from_hz) ** travelled
        f = 2.0 * math.sin(math.pi * min(cutoff, RATE * 0.22) / RATE)
        low += f * band
        band += f * (sample - low - damping * band)
        buffer[i] = low


def low_pass(buffer, cutoff, passes=2):
    """A plain one-pole low-pass, run twice. This takes the last edge off."""
    smoothing = 1.0 - math.exp(-2.0 * math.pi * cutoff / RATE)
    for _ in range(passes):
        held = 0.0
        for i, value in enumerate(buffer):
            held += (value - held) * smoothing
            buffer[i] = held


def echo(buffer, spacing, repeats=4, feedback=0.42):
    """Repeats spaced off a beat: the delay every synth record leans on.

    Taken from a copy of the buffer rather than fed back through it, so the
    repeats cannot compound into a howl.
    """
    source = list(buffer)
    for repeat in range(1, repeats + 1):
        offset = int(spacing * repeat * RATE)
        gain = feedback ** repeat
        for i in range(offset, len(buffer)):
            buffer[i] += source[i - offset] * gain


def tail(buffer, taps=((0.11, 0.30), (0.19, 0.21), (0.31, 0.14), (0.47, 0.08))):
    """Soft echoes behind the note, so it ends in a room rather than a cut."""
    source = list(buffer)
    for delay, gain in taps:
        offset = int(delay * RATE)
        for i in range(offset, len(buffer)):
            buffer[i] += source[i - offset] * gain


def write(name, buffer):
    """Normalise, fade both ends and write a 16-bit mono WAV."""
    peak = max(abs(v) for v in buffer) or 1.0
    scale = PEAK / peak
    fade_in = int(0.006 * RATE)
    fade_out = int(0.30 * RATE)
    frames = bytearray()
    for i, value in enumerate(buffer):
        value *= scale
        if i < fade_in:
            value *= i / fade_in
        remaining = len(buffer) - i
        if remaining < fade_out:
            value *= remaining / fade_out
        frames += struct.pack("<h", int(max(-1.0, min(1.0, value)) * 32767))

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(bytes(frames))
    print("wrote %s (%.2fs)" % (path, len(buffer) / RATE))


# ============ The pair the game plays ============

def won():
    """A run up a major chord on a detuned synth, landing on the chord held,
    with the filter opening the whole way: the sound of something coming up to
    power."""
    buffer = [0.0] * int(3.2 * RATE)

    # The run up. Short notes, close together, so it reads as a sequencer.
    for i, freq in enumerate((261.63, 392.00, 523.25, 659.25, 783.99, 1046.50)):
        voice(buffer, i * 0.075, freq, 0.22, 0.005, 0.26, length=1.1,
              harmonics=8, detune=0.010, voices=3, rolloff=1.15)

    # The chord it lands on, arriving with the top note of the run.
    for freq in (261.63, 329.63, 392.00, 523.25):  # C4 E4 G4 C5
        voice(buffer, 0.45, freq, 0.24, 0.04, 1.45, harmonics=8, detune=0.013,
              voices=3, rolloff=1.30)

    # Sub underneath, and a bell over the top.
    voice(buffer, 0.45, 65.41, 0.30, 0.008, 0.85, harmonics=2, rolloff=2.4)
    voice(buffer, 0.47, 1046.50, 0.10, 0.004, 1.10, harmonics=3, rolloff=2.6)

    # Open from almost shut to wide, fast at first: the chord blooms.
    sweep_filter(buffer, 420.0, 5400.0, resonance=1.35, over=0.85, curve=0.55)
    echo(buffer, 0.195, repeats=4, feedback=0.40)
    low_pass(buffer, 8000, passes=1)
    write("round_won.wav", buffer)


def lost():
    """A run down onto a minor chord, with the filter closing and the pitch
    sagging: the same machine losing power instead of finding it."""
    buffer = [0.0] * int(3.4 * RATE)

    # Down by a semitone first. The half step is what makes it sound wrong
    # rather than merely sad.
    for i, freq in enumerate((440.00, 415.30, 349.23, 293.66)):  # A4 G#4 F4 D4
        voice(buffer, i * 0.125, freq, 0.22, 0.006, 0.30, length=1.2,
              harmonics=7, detune=0.012, voices=3, rolloff=1.25)

    # The chord it lands on, bending flat as it goes.
    for freq in (146.83, 174.61, 220.00):  # D3 F3 A3
        voice(buffer, 0.56, freq, 0.26, 0.07, 1.60, harmonics=7, detune=0.014,
              voices=3, rolloff=1.35, glide=0.975)

    # The sub drops much further than the chord: the floor going out.
    voice(buffer, 0.56, 73.42, 0.30, 0.02, 1.25, harmonics=2, rolloff=2.4,
          glide=0.80)

    # Close it down slowly, and further than the ear expects.
    sweep_filter(buffer, 4600.0, 240.0, resonance=1.30, over=2.10, curve=0.85)
    echo(buffer, 0.225, repeats=4, feedback=0.38)
    low_pass(buffer, 5200, passes=1)
    write("round_lost.wav", buffer)


# ============ The plainer pair, kept as a fallback ============

def won_chime():
    """A climb into a major chord, struck rather than played."""
    buffer = [0.0] * int(3.0 * RATE)

    for i, freq in enumerate((523.25, 659.25, 783.99)):  # C5 E5 G5
        voice(buffer, i * 0.13, freq, 0.34, 0.012, 0.75, harmonics=5, detune=0.004,
              voices=2)

    for freq in (261.63, 329.63, 392.00, 523.25):  # C4 E4 G4 C5
        voice(buffer, 0.40, freq, 0.30, 0.09, 1.55, harmonics=4, detune=0.003,
              voices=2, rolloff=1.9)

    voice(buffer, 0.40, 1046.50, 0.13, 0.02, 1.40, harmonics=3, rolloff=2.4)
    voice(buffer, 0.40, 130.81, 0.22, 0.05, 1.30, harmonics=3, rolloff=2.2)

    low_pass(buffer, 4200)
    tail(buffer)
    write("round_won_chime.wav", buffer)


def lost_chime():
    """A fall into a minor chord, struck rather than played."""
    buffer = [0.0] * int(3.2 * RATE)

    for i, freq in enumerate((440.00, 349.23, 293.66)):  # A4 F4 D4
        voice(buffer, i * 0.20, freq, 0.32, 0.016, 0.70, harmonics=4, detune=0.005,
              voices=2, rolloff=1.9)

    for freq in (146.83, 174.61, 220.00):  # D3 F3 A3
        voice(buffer, 0.62, freq, 0.34, 0.16, 1.70, harmonics=4, detune=0.004,
              voices=2, rolloff=2.0, glide=0.985)

    voice(buffer, 0.62, 73.42, 0.26, 0.10, 1.50, harmonics=3, rolloff=2.3, glide=0.96)

    low_pass(buffer, 2600)
    tail(buffer)
    write("round_lost_chime.wav", buffer)


if __name__ == "__main__":
    won()
    lost()
    won_chime()
    lost_chime()
