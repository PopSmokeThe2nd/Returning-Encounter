ProDG stand-in compiler
=======================

The game code was built with SN Systems ProDG, a g++ 2.95.3 derivative. Its compiler
(`ngccc.exe`) is a Windows program. This directory builds a stand-in that runs natively on Linux:
upstream GCC 2.95.3's `cc1plus` for `powerpc-eabi`, with a small patch
(`prodg-standin.patch`). With the flags and environment `compile.py` uses, it reproduces all 18
functions of `src/game/NetricsaObject.cpp` instruction for instruction (relocations compared by
kind and target; data contents not compared). Seven of those were written against the stand-in
and then confirmed with the real compiler: the description of
[PR #5](https://github.com/PopSmokeThe2nd/Returning-Encounter/pull/5) records the objdiff results
of the real ProDG build, all 18 functions at 100%.

**It is a stand-in, not the reference.** The patch was tuned on one unit, and ProDG may differ
from upstream 2.95.3 in ways that unit doesn't exercise. The final word is always the real ProDG
build and objdiff on Windows. If the stand-in and ProDG disagree, ProDG is right, and the patch
needs work.

Usage
-----

First set up the normal build as described in the [top-level README](../../README.md#building):
put your disc image in `orig/G3BE9G` (decomp-toolkit needs the game's DOL) and run
`python configure.py && ninja` once. `compare.py` compares against decomp-toolkit's assembly for
the unit, which that build writes to `build/G3BE9G/asm`. Then:

```sh
python tools/standin/build.py
python tools/standin/compile.py src/game/NetricsaObject.cpp
python tools/standin/compare.py build/standin/obj/src/game/NetricsaObject.o build/G3BE9G/asm/game/NetricsaObject.s
```

`compile.py` writes `build/standin/obj/src/game/NetricsaObject.o`. The compare should print
`MATCH` for every function, then `18/18 functions match`. Add `-v` to see the differing
instructions of a `DIFF`.

### Requirements

- Linux on x86-64 (on Windows, use WSL). macOS can't build it (no 32-bit x86 toolchain), but
  `compare.py` runs anywhere.
- Python 3.8 or later, `make`, and a gcc that can build 32-bit programs
  (Debian/Ubuntu: `sudo apt install gcc-multilib`).
- Network access to `raw.githubusercontent.com` (GCC sources), and to `github.com` and
  `release-assets.githubusercontent.com` (binutils, a GitHub release download that redirects
  there).

build.py
--------

1. Downloads the files listed in `files.txt` from the `releases/gcc-2.95.3` tag of the
   [gcc-mirror](https://github.com/gcc-mirror/gcc) repository into `build/standin/src`. Files
   already there are skipped, failed downloads are retried, and a rerun picks up where it stopped.
   Every download is checked against its sha256 in `files.txt`, and so is every unpatched file on
   each run. A file that doesn't match is deleted (or not saved) and `build.py` stops with an
   error naming it; rerun to download it again.
2. Applies `prodg-standin.patch` with a built-in patcher, so `patch` isn't needed. It checks every
   hunk before changing any file, and stops if any hunk doesn't apply. The sha256 of each patched
   file goes into `build/standin/src/.standin-patch`. If the patch changes later, or a patched
   file is deleted or edited, pristine copies of those files are downloaded and patched again, and
   `cc1plus` is rebuilt. So change the patch, not the files in `build/standin/src`.
3. Configures GCC (`--target=powerpc-eabi --enable-languages=c++`) in `build/standin/gcc` and
   runs `make cc1plus`, then copies the result to `build/standin/cc1plus`. Logs go to
   `build/standin/logs`. This takes about a minute.
4. Downloads the `powerpc-eabi` binutils into `build/binutils` with `tools/download_tool.py` and
   the `binutils_tag` from `configure.py`, like `ninja` does. If they're already there, nothing
   is downloaded.

Rerunning it does nothing when everything is up to date. A change to the patch, `files.txt`
or the build recipe rebuilds `cc1plus` from scratch. `--force` also rebuilds it. Use `--out DIR`
and `--binutils DIR` to put the results somewhere else, and `--help` for the other options.

Building GCC 2.95.3 with a current toolchain needs some workarounds. `build.py` handles them:

- GCC 2.95 assumes 32-bit `long` and pointers, so the host compiler is `gcc -m32`.
- Host `CFLAGS` are `-O1 -g -w -std=gnu89 -fcommon -fno-strict-aliasing`. `-std=gnu89` and
  `-fcommon` keep the old C building. `-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0
  -fno-stack-protector` stop glibc's checks from aborting `cc1plus` ("buffer overflow
  detected") on code that is correct for its time. When the host gcc accepts `-fpermissive` for C
  (gcc 14 and later), it is added so that old-C warnings newer gcc versions turn into errors stay
  warnings.
- The Makefiles regenerate `configure`, `config.in`, the parser (`cp/parse.c`) and the keyword
  table (`cp/hash.h`) when their inputs look newer. Downloading gives files
  arbitrary timestamps, and a modern autoconf, bison or gperf produces broken or different
  files. `build.py` therefore gives every source the GCC 2.95.3 release date and the generated
  files slightly later times. Stub `autoconf`/`autoheader`/`bison`/`yacc`/`gperf`/`makeinfo`
  on `PATH` fail loudly if make still tries to run them.
- `configure` fills `options.h` from `gcc/cp/lang-options.h`, which must be present before it
  runs. Otherwise `cc1plus` rejects `-fno-rtti`. `build.py` checks for this.
- Scripts are made executable and `configure` runs under `/bin/sh`.
- If parallel make fails, it continues once with `-j1` before giving up.

`files.txt` lists the 201 GCC files that `configure` and `make cc1plus` read or check for, each
with the sha256 of the upstream file, in the format `sha256sum -c` reads. The list comes from
tracing a build with `strace`. Nothing else from GCC is downloaded.

compile.py
----------

Compiles one C++ file the way the ProDG rule in `configure.py` would, but with the stand-in:

1. Preprocesses it with the host's `gcc -E -x c++ -nostdinc -undef -std=gnu++98` (or `clang`,
   or `--cpp`). It uses the unit's `-I`/`-D` flags from `build.ninja`, or the same defaults as
   `cflags_game` in `configure.py` if `build.ninja` doesn't exist. If `build.ninja` exists but
   doesn't build the file with the ProDG rule, it warns and uses those defaults. `-undef` drops
   the host's target and system macros. The ones GCC 2.95.3's driver defines for powerpc-eabi
   are added instead: `__GNUC__=2`, `__GNUC_MINOR__=95`, `__GNUG__=2`, `PPC`, `__PPC__`,
   `__PPC`, `__embedded__`, `_ARCH_PPC`, `_CALL_SYSV`, `_BIG_ENDIAN`, `__BIG_ENDIAN__` and
   `__CHAR_UNSIGNED__`, plus `__OPTIMIZE__` for `-O` levels above `-O0`, as 2.95's driver does.
   A few of the host's own survive `-undef`: gcc keeps `__STDC__` and `__cplusplus` (as
   `199711L`, where g++ 2.95 has `1`), plus `__STDC_HOSTED__` and `_GNU_SOURCE`, which 2.95
   doesn't define. clang keeps a few others instead (`__STDC_UTF_16__`, `__STDC_UTF_32__`,
   `__STDCPP_*`, `__GCC_HAVE_DWARF2_CFI_ASM`) and not `_GNU_SOURCE`. ProDG's driver might define
   more of its own.
2. Runs `cc1plus -quiet -O2 -mcpu=750 -mmultiple -msdata=sysv -G 8 -fno-rtti -fno-exceptions`
   with `PRODG_FMR1=1 PRODG_CMP=1 PRODG_STORE=2` in the environment (see the patch below).
3. Assembles with `powerpc-eabi-as -mbig -mregnames -many`.

Options: `-o` sets the output (default `build/standin/obj/<path>.o`). `-S` stops at assembly.
`--keep` keeps the `.ii` and `.s` next to the object. `-v` prints the commands. For experiments,
use `--cc1=-fno-schedule-insns2` to pass an extra flag to `cc1plus`, and `--env PRODG_STORE=3`
(or `--env PRODG_STORE=` to unset it) to change the environment. Other `PRODG_*` variables in
the environment are removed, with a warning naming them, so a leftover `export` can't change
the output. The preprocessor's line markers are kept, so `cc1plus` reports errors against the
source files and their lines.

compare.py
----------

Compares each function in an object with the same function in dtk's `.s` for the unit, and
prints `MATCH` or `DIFF`. Functions are paired by name. They match once `symbols.txt` has the
mangled names. Use `--map file` with `target_name = our_name` lines when the names differ.

Each instruction is compared as a 32-bit word with its relocated bits masked out, plus its
relocation: the same kind (`@ha`, `@l`, `@sda21`, branch) and the same target. Symbols are
compared by name when both sides use the name. A reference to the unit's own data (string
literals, float constants, vtables not named in `symbols.txt` yet) is compared as section +
offset, so the data layout must match too. The data contents themselves are not compared; use
objdiff for that. `-v` prints a diff of the differing instructions. Our side is disassembled with
`powerpc-eabi-objdump` from `build/binutils`, and the diff is computed on the masked words and
relocations, not the text. `-f NAME` limits the compare to one function. The exit status is 0
only if every function matches, with nothing missing and nothing extra.

The patch
---------

`prodg-standin.patch` is a unified diff against the upstream GCC 2.95.3 files. Each change is
needed for `NetricsaObject.cpp` to match:

- `gcc/config/rs6000/rs6000.c`, `easy_fp_constant()`: non-zero float constants are never "easy",
  so they always load from the constant pool with `lis` + `lfs sym@l(rN)` like ProDG does, where
  upstream emits `addi` + `lfs 0(rN)` (`CreateModel__21CcNetricsaEnemyObjectPv`; no float
  constant anywhere in the game is built in a GPR). `PRODG_EASY_FP=1` restores upstream.
- `gcc/config/rs6000/rs6000.h`, `ELIMINABLE_REGS` (a comment hunk and the change): drops the
  `{ 30, 30 }` entry, so r30 is an ordinary callee-saved register. Upstream makes it eliminable
  for `-mminimal-toc`, the allocators avoid it, and 7 functions save r29-r31 where ProDG saves
  r30-r31.
- `gcc/expmed.c`, `emit_store_flag()`: no branch-free `x != 0` (`neg`/`or`/`srwi`), so the value
  comes from a compare and branch as in `CreateModel__21CcNetricsaEnemyObjectPv`. None of the
  game's 386k instructions use that sequence. `PRODG_NE_SCC=1` restores upstream.
- `gcc/haifa-sched.c`, `insn_cost()`: latencies from the environment for FP register copies
  (`PRODG_FMR1`), stores (`PRODG_STORE`) and integer compares (`PRODG_CMP`), set to 1/2/1 by
  `compile.py` so the PPC750 schedule matches ProDG's. Unset means upstream costs. Each is needed:
  without `PRODG_FMR1` both `UpdateModel` functions differ, without `PRODG_CMP` two
  `CreateModel` functions, and without `PRODG_STORE` the `CcNetricsaObject` constructor and
  `CreateModel__26CcNetricsaEnemyPartsObjectPv`.

Experiments from the session that built the stand-in were dropped. `NetricsaObject.cpp` still
matches 18/18 without them:

- `local-alloc.c`: other qsort implementations (`altqsort.h`, `QSORT`), tie-break orders
  (`QTIE`, `QREV`) and a debug dump (`QDBG`). The comparators already break ties by quantity
  number, so the sort algorithm can't change the result.
- `haifa-sched.c`: `PRODG_ANTI0`, zero-cost anti-dependences.
- `rs6000.c`: `PRODG_ISSUE`, an issue-rate override.

Known limits
------------

- C++ only. The stand-in has no `cc1`, so `.c` units can't be compiled.
- The scheduler latencies were fitted to one unit. Other code may need more tuning, or show
  ProDG changes that upstream 2.95.3 doesn't have.
- GCC uses host floating point for some heuristics (register allocation priorities) and for
  constant folding. The stand-in uses x87 math as a 32-bit Linux program, and ProDG used
  whatever its Windows build used, so rare near-ties could break differently.
- Preprocessing uses the host's preprocessor, so the predefined macros differ from 2.95's in the
  ways listed under `compile.py` above.

License
-------

`prodg-standin.patch` is licensed under the GNU General Public License, version 2 or later
(GPL-2.0-or-later), like GCC 2.95.3: it modifies GCC, so it is a derivative of GCC. The scripts
in this directory (`build.py`, `compile.py`, `compare.py`) and `files.txt` follow the
repository's licence, which hasn't been chosen yet.

The built `cc1plus` is GPL software too. If you share a binary, share its corresponding source
with it: the upstream files listed in `files.txt`, at the `releases/gcc-2.95.3` tag, plus
`prodg-standin.patch`, `build.py` (which applies the patch and holds the configure and make
settings) and `files.txt`. No GCC source or binary is committed to this repository. Everything
is downloaded or built under `build/`, which git ignores.

Changes by the Returning-Encounter project, 2026-10-21: `easy_fp_constant()` in
`gcc/config/rs6000/rs6000.c`, `ELIMINABLE_REGS` in `gcc/config/rs6000/rs6000.h`,
`emit_store_flag()` in `gcc/expmed.c` and `insn_cost()` in `gcc/haifa-sched.c`, as described
under "The patch" above. Each change is marked "ProDG stand-in" in the source.
