# Audio masters

Kept outside `client/` on purpose: Godot imports everything under the project
directory, so anything in here would otherwise be converted and shipped.
Nothing in this folder is loaded by the game.

## What is here

| file | what it is |
|------|------------|
| `shop_music_original.wav` | exactly what Stable Audio gave us, untouched |
| `shop_music_loop_lossless.wav` | the loop, cut and crossfaded, before encoding |
| `seamless_loop.py` | cuts a standalone loop that joins end to start |
| `loop_point.py` | keeps an intro and loops back to a point after it |

`client/assets/audio/shop_music.ogg` is `shop_music_loop_lossless.wav` encoded
with `oggenc -q 6`. To change quality, re-encode from the lossless file rather
than from the ogg -- encoding an encode compounds the artefacts of both.

    oggenc -q 6 -o client/assets/audio/shop_music.ogg \
        audio_masters/shop_music_loop_lossless.wav

Measured error against the lossless file, in the 2-6 kHz band where this
material shows codec trouble first:

    q4   1.06 MB   -12.5 dB      q9   2.54 MB   -29.1 dB
    q6   1.54 MB   -16.3 dB      q10  3.69 MB   -37.8 dB
    q8   2.04 MB   -24.1 dB

## Two things that cost time

The original is **not** lossless despite being a .wav: its content stops dead
at 16.9 kHz, which is a codec lowpass. It was decoded from something
compressed. So every encode from it is lossy-on-lossy, which is why the
quality had to go higher than usual to sound clean.

Godot's WAV importer and `AudioStreamWAV` disagree about what the loop numbers
mean -- the importer is `0=Detect, 1=Disabled, 2=Forward`, the runtime is
`0=Disabled, 1=Forward`. Ogg is spared this: it takes a plain `loop=true`.
Editing a `.import` by hand also does not force a reimport; delete
`.godot/imported/<name>-*` or the old asset is what gets tested.
