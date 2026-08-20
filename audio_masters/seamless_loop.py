#!/usr/bin/env python3.13
"""Cut a seamless loop out of a generated track.

    seamless_loop.py IN OUT [--bpm 90] [--bars 16] [--start 8.0] [--fade 1.5]

The trick is not to fade the end into silence, which is audible as a dip.
The tail is crossfaded *over the head*, so the last moment of the loop is
already the first moment: playing it end to end has nothing to give away.
"""
import argparse, sys
import numpy as np
import soundfile as sf


def equal_power(n):
    """A crossfade that holds its loudness through the middle.

    A straight linear fade dips in the centre, because two uncorrelated
    signals at half amplitude are quieter than either at full.
    """
    t = np.linspace(0.0, 1.0, n, dtype=np.float64)
    return np.cos(t * np.pi / 2.0), np.sin(t * np.pi / 2.0)


def best_end(audio, rate, start, want, search, probe=0.25):
    """Where to cut, so the join is between two moments that already agree.

    Looks around the wanted length for the point whose surrounding audio most
    resembles the audio at the loop's start, so the crossfade has the least
    work to do. Mono, coarse, and only ever a hint -- the crossfade is what
    actually hides the join.
    """
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    probe_n = int(probe * rate)
    head = mono[start:start + probe_n]
    head = head - head.mean()
    if not np.any(head):
        return start + want
    best, score = start + want, -np.inf
    lo = max(start + probe_n, start + want - search)
    hi = min(len(mono) - probe_n, start + want + search)
    for end in range(lo, hi, max(1, int(0.01 * rate))):
        tail = mono[end - probe_n:end]
        tail = tail - tail.mean()
        denom = np.linalg.norm(tail) * np.linalg.norm(head)
        if denom == 0:
            continue
        match = float(np.dot(tail, head) / denom)
        if match > score:
            best, score = end, match
    return best


def main():
    p = argparse.ArgumentParser()
    p.add_argument("infile")
    p.add_argument("outfile")
    p.add_argument("--bpm", type=float, default=90.0)
    p.add_argument("--bars", type=int, default=16)
    p.add_argument("--beats-per-bar", type=int, default=4)
    p.add_argument("--start", type=float, default=0.0,
                   help="seconds in to begin, past any intro")
    p.add_argument("--fade", type=float, default=1.5, help="crossfade seconds")
    p.add_argument("--search", type=float, default=0.0,
                   help="seconds either side to hunt for a better cut")
    a = p.parse_args()

    audio, rate = sf.read(a.infile, always_2d=True, dtype="float64")
    bar = a.beats_per_bar * 60.0 / a.bpm
    want = int(round(a.bars * bar * rate))
    start = int(round(a.start * rate))
    fade = int(round(a.fade * rate))

    if a.search > 0:
        end = best_end(audio, rate, start, want, int(a.search * rate))
    else:
        end = start + want
    if end + fade > len(audio):
        end = len(audio) - fade
    if end - start <= fade:
        sys.exit("not enough audio: shorten --bars or --fade")

    body = audio[start:end].copy()
    tail = audio[end:end + fade].copy()
    out_g, in_g = equal_power(fade)
    body[:fade] = body[:fade] * in_g[:, None] + tail * out_g[:, None]

    sf.write(a.outfile, body, rate)
    print("%s -> %s" % (a.infile, a.outfile))
    print("  loop %.2fs (%d bars at %g BPM), cut at %.2fs, %.2fs crossfade"
          % (len(body) / rate, a.bars, a.bpm, end / rate, a.fade))


if __name__ == "__main__":
    main()
