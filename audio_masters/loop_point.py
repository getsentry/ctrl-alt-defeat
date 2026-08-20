#!/usr/bin/env python3.13
"""Bake a loop point into a track that keeps its intro.

Godot's looping is a hard jump: at the end of the stream it continues from
`loop_begin`. There is no crossfade, so the file has to be built such that
the jump lands on matching audio.

So the crossfade goes at the *end* of the file, blending the real ending into
the moment just before the loop point. Played through, the intro is heard
once; at the end the audio has already become what comes before the loop
point, and the jump continues it. Nothing gives the join away.

    loop_point.py IN OUT --loop-at 28 --drop-tail 2 --fade 5
"""
import argparse, sys
import numpy as np
import soundfile as sf


def equal_power(n):
    t = np.linspace(0.0, 1.0, n, dtype=np.float64)
    return np.cos(t * np.pi / 2.0), np.sin(t * np.pi / 2.0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("infile")
    p.add_argument("outfile")
    p.add_argument("--loop-at", type=float, required=True,
                   help="seconds; where playback returns to")
    p.add_argument("--drop-tail", type=float, default=0.0,
                   help="seconds of the ending to throw away")
    p.add_argument("--fade", type=float, default=5.0)
    a = p.parse_args()

    audio, rate = sf.read(a.infile, always_2d=True, dtype="float64")
    end = len(audio) - int(round(a.drop_tail * rate))
    loop = int(round(a.loop_at * rate))
    fade = int(round(a.fade * rate))

    if loop < fade:
        sys.exit("--loop-at must be at least --fade seconds in")
    if end - loop <= fade:
        sys.exit("loop too short for that crossfade")

    out = audio[:end].copy()
    # The last `fade` seconds become the ending turning into the run-up to the
    # loop point, so that the jump back continues rather than restarts.
    ending = out[end - fade:end]
    run_up = audio[loop - fade:loop]
    out_g, in_g = equal_power(fade)
    out[end - fade:end] = ending * out_g[:, None] + run_up * in_g[:, None]

    sf.write(a.outfile, out, rate)
    print("%s -> %s" % (a.infile, a.outfile))
    print("  plays %.2fs, loops back to %.2fs, loop is %.2fs long, %.1fs crossfade"
          % (end / rate, a.loop_at, (end - loop) / rate, a.fade))
    print("  loop_begin = %d samples" % loop)


if __name__ == "__main__":
    main()
