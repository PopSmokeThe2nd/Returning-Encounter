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

Early. The build rebuilds a byte-identical `main.dol`, game code compiles with SN ProDG, and the
first game file (`src/game/NetricsaObject.cpp`) is being decompiled.

What we know about the binary:

| | |
|---|---|
| Build string | `Build FINAL.107 (Jan 22 2004 @ 12:04:50)` |
| Game code compiler | SN Systems ProDG (GCC 2.95). The runtime reports libsn version 59, one older than ProDG 3.9.3, so the build uses 3.9.3 with `-O2`. |
| Dolphin SDK | Sep 5 2002 release builds (`0x2301`), compiled by Nintendo with Metrowerks |
| Symbols | None ship on the disc. About 710 library functions are named by matching other decompiled games, see [docs/split-map.md](docs/split-map.md#library-names). |
| Modules | `main.dol` only, no `.rel` files |

Memory layout of `main.dol`:

| Section | Address | Size | Notes |
|---|---|---|---|
| `.init` | `0x80003100` | `0x3A0` | Startup code |
| `.text` | `0x800034A0` | `0x1DD8A0` | Game code first, then the libsn debug stub at `0x8017BF90`, then SDK and libraries |
| `.ctors.dtors` | `0x801E0D40` | `0x260` | GCC-style constructor and destructor tables, merged |
| `.rodata` | `0x801E0FC0` | `0x573C0` | |
| `.data` | `0x80238380` | `0x37320` | |
| `.bss` | `0x8026F6A0` | `0x6A500` | |
| `.sdata` | `0x802D9BA0` | `0x1F00` | |
| `.sbss` | `0x802DBAA0` | `0xD24` | |
| `.sdata2` | `0x802DC7E0` | `0x1360` | |

Known problem areas for analysis:

- `0x8017BF90`–`0x8017E350` is a hand-written SN Systems debug monitor. It uses
  non-standard link-register conventions, `rfi`, and self-modifying stubs, so it is excluded
  from control-flow analysis in `config/G3BE9G/config.yml` and will stay as assembly.
- The startup code clears `.sbss` up to `0x802DC7C4`, the address right after the section.
  That address isn't inside any section, so those two instructions are left as absolute values
  (`block_relocations` in `config.yml`). Without this, decomp-toolkit 1.8.4 runs out of memory.
- ProDG's linker merged `.ctors` and `.dtors` into one DOL section (`0x801E0D40`, with `.dtors`
  starting at `0x801E0F20`). It is named `.ctors.dtors` for now, because decomp-toolkit expects
  `.ctors` to end at its null terminator.

- ProDG reaches `.sdata2` through `r13`, the same base register as `.sdata`. Its crt0 sets `r2`
  to `0x802F1BA0` but nothing uses it. mwld follows the EABI and resolves `.sdata2` through
  `r2`, so `tools/sn_elf2dol.py` rewrites those accesses to `r13` after linking
  (`config.sn_small_data` in `configure.py`). The `r2` setup in `__start` is kept as an
  absolute value.

With those settings, `ninja` runs decomp-toolkit through the whole DOL. It finds about 7,900
functions and 20,000 symbols and recognizes some Dolphin SDK functions (GX, OS) by signature. The
split objects relink into a byte-identical `main.dol`.

Game code is split into 109 groups of whole source files, found from the game's static
constructors, plus files found inside those groups. See [docs/split-map.md](docs/split-map.md)
for the layout and what's left to split.

Compiling game code
-------------------

Game units are compiled with `ngccc.exe` from SN Systems ProDG, which the build downloads along
with the Metrowerks compilers (`build/compilers/ProDG/<version>`). Add a unit to the `GameLib`
in `configure.py` and it gets the ProDG rule. Things to know when writing matching code:

- ProDG is g++ 2.95, so C++ uses the old GNU name mangling (`__16CcNetricsaObjectiRC6VECTOR`,
  `_._16CcNetricsaObject` for destructors, `_vt.16CcNetricsaObject` for vtables). ProDG uses `.`
  where other g++ 2.95 builds use `$`. Rename a function in `config/G3BE9G/symbols.txt` to its
  mangled name so objdiff pairs it up.
- Classes put their vtable pointer after their own fields. Vtable entries are 8 bytes: an offset
  for `this` and the function pointer.
- `new` and `delete` are inline in the game (`include/game/memory.h`), so every `delete`
  expands to the pool and heap code.
- Functions that aren't identified yet are declared `extern "C"` with their `fn_<address>`
  name, so calls to them match without inventing a class.

Without ProDG at hand, [tools/standin](tools/standin/README.md) builds a Linux stand-in: GCC
2.95.3's `cc1plus` with a small patch, which reproduces ProDG's output for the one unit
decompiled so far, `src/game/NetricsaObject.cpp`. It's for quick iteration only; the real ProDG
build and objdiff stay the reference. After a normal build (see [Building](#building)):

```sh
python tools/standin/build.py
python tools/standin/compile.py src/game/NetricsaObject.cpp
python tools/standin/compare.py build/standin/obj/src/game/NetricsaObject.o build/G3BE9G/asm/game/NetricsaObject.s
```

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
