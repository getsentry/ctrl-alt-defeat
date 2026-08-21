# noto_symbols_subset.ttf

Six glyphs, and nothing else:

| glyph | codepoint | where it is drawn |
|-------|-----------|-------------------|
| ⚔ | U+2694 | the versus mark between the two fighters |
| ▶ | U+25B6 | play, on the battle screen |
| ❚ | U+275A | pause, the same button |
| ✕ | U+2715 | closing the battle log |
| ★ | U+2605 | a star zone, in an item's description |
| ◆ | U+25C6 | a diamond zone, in the same place |

Godot ships Open Sans with no fallbacks and Open Sans has none of them. A
desktop build hides that by asking the operating system for a font that does;
a browser gives it nothing to ask, so every one of these was a box on the web.

Cut from Noto Sans Symbols 2 (the first five) and Noto Sans Symbols (the
swords) with `fonttools subset`, then merged. Both are Google's Noto, licensed
under the SIL Open Font License 1.1 with no reserved font name -- OFL.txt is
beside this file, and the copyright and licence fields are still inside the
font itself. 2.6KB, against 915KB for the two fonts whole.

To add a glyph: subset it out of the Noto font that has it and merge again,
then say so in `scripts/symbols.gd`'s test, which is what would have caught
this in the first place.
