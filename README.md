Returning Encounter
===================

A work-in-progress decompilation of **Serious Sam: Next Encounter** for the Nintendo GameCube
(Climax Solent, 2004).

The long-term goal is a native PC port built from the decompiled code, in the same way the
Mario Party 4, Super Mario Sunshine and Twilight Princess decompilations led to PC ports.

This repository does **not** contain any game assets, executables or disassembly.
You need your own copy of the game, dumped from your own disc.

Supported versions:

- `G3BE9G`: USA, Rev 1 (`main.dol` SHA-1 `99178f5503e2d51714890c11619518c9ffb07d04`)

Status
======

Early setup. Nothing is decompiled yet.

What we know about the binary:

| | |
|---|---|
| Build string | `Build FINAL.107 (Jan 22 2004 @ 12:04:50)` |
| Game code compiler | SN Systems ProDG (GCC-based). Exact version not yet identified. |
| Dolphin SDK | Sep 5 2002 release builds (`0x2301`), compiled by Nintendo with Metrowerks |
| Symbols | None. No map file or debug info ships on the disc. |
| Modules | `main.dol` only, no `.rel` files |

Memory layout of `main.dol`:

| Section | Address | Size | Notes |
|---|---|---|---|
| `.init` | `0x80003100` | `0x3A0` | Startup code |
| `.text` | `0x800034A0` | `0x1DD8A0` | Game code first, then the libsn debug stub at `0x8017BF90`, then SDK and libraries |
| `.ctors` / `.dtors` | `0x801E0D40` | `0x260` | GCC-style constructor/destructor tables |
| `.rodata` | `0x801E0FC0` | `0x573C0` | |
| `.data` | `0x80238380` | `0x37320` | |
| `.bss` | `0x8026F6A0` | `0x6D124` | Includes `.sdata` and `.sbss` |
| `.sdata` | `0x802D9BA0` | `0x1F00` | |
| `.sdata2` | `0x802DC7E0` | `0x1360` | |

Known problem areas for analysis:

- `0x8017BF90`–`0x8017E350` is a hand-written SN Systems debug monitor. It uses
  non-standard link-register conventions, `rfi`, and self-modifying stubs, so it is excluded
  from control-flow analysis in `config/G3BE9G/config.yml` and will stay as assembly.
- With that range excluded, decomp-toolkit's analysis finds about 7,900 functions, and it
  recognizes Dolphin SDK functions such as the GX library automatically. The split step that
  follows currently crashes (out of memory while applying relocations), so `ninja` does not
  produce objects yet. This is being worked on.

Dependencies
============

Windows
-------

- Install [Python](https://www.python.org/downloads/) and add it to `%PATH%`.
- Install [ninja](https://github.com/ninja-build/ninja/releases) and add it to `%PATH%`
  (or run `pip install ninja`).

macOS
-----

- Install [ninja](https://github.com/ninja-build/ninja/wiki/Pre-built-Ninja-packages): `brew install ninja`

[wibo](https://github.com/decompals/wibo) is downloaded automatically to run the Metrowerks tools.

Linux
-----

- Install [ninja](https://github.com/ninja-build/ninja/wiki/Pre-built-Ninja-packages).

[wibo](https://github.com/decompals/wibo) is downloaded automatically to run the Metrowerks tools.

Building
========

1. Clone the repository.
2. Put your disc image in `orig/G3BE9G`. Supported formats include ISO (GCM), RVZ, WIA, CISO and GCZ.
   An extracted disc also works: copy the `sys` and `files` folders into `orig/G3BE9G`.
3. Configure:

   ```sh
   python configure.py
   ```

4. Build:

   ```sh
   ninja
   ```

The first build runs [decomp-toolkit](https://github.com/encounter/decomp-toolkit) to analyze
`main.dol` and split it into objects under `build/G3BE9G`.

Diffing
=======

Once the initial build succeeds, an `objdiff.json` exists in the project root.

Download the latest release of [objdiff](https://github.com/encounter/objdiff), open it, and
set the project directory to this repository. objdiff rebuilds and diffs automatically as you edit
source files.

Project structure
=================

- `configure.py`: project configuration and build generator (compiler flags, object status).
- `config/G3BE9G/`: decomp-toolkit configuration (`config.yml`, `symbols.txt`, `splits.txt`, `build.sha1`).
- `orig/G3BE9G/`: your game files. Ignored by git.
- `src/`, `include/`: decompiled C/C++ source and headers.
- `tools/`: build scripts from [dtk-template](https://github.com/encounter/dtk-template).
- `docs/`: decomp-toolkit configuration reference from dtk-template.

References
==========

- [decomp-toolkit](https://github.com/encounter/decomp-toolkit)
- [objdiff](https://github.com/encounter/objdiff)
- [decomp.me](https://decomp.me)
- [GC/Wii Decompilation Discord](https://discord.gg/hKx3FJJgrV)
