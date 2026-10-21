#!/usr/bin/env python3

###
# Compiles one C++ file with the ProDG stand-in compiler (see README.md).
#
# Usage:
#   python tools/standin/compile.py src/game/NetricsaObject.cpp
#   (writes build/standin/obj/src/game/NetricsaObject.o)
#
# Steps:
#   1. preprocess with the host's gcc: gcc -E -x c++ -nostdinc, with the
#      -I/-D flags configure.py gives ProDG units
#   2. compile with build/standin/cc1plus and ProDG's code generation flags
#   3. assemble with powerpc-eabi-as from build/binutils
#
# Run tools/standin/build.py first.
###

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent
EXE = ".exe" if os.name == "nt" else ""

# What SN ProDG's driver passes to its cc1plus for GameCube code, as far as
# the matched code shows: PowerPC 750 scheduling, lmw/stmw, SVR4 small data
# for objects up to 8 bytes, no RTTI and no exceptions.
CC1PLUS_FLAGS = [
    "-mcpu=750",
    "-mmultiple",
    "-msdata=sysv",
    "-G",
    "8",
    "-fno-rtti",
    "-fno-exceptions",
]

# Scheduler latencies for the patched haifa-sched.c (prodg-standin.patch).
# With these values the stand-in reproduces ProDG's instruction order.
PRODG_ENV = {
    "PRODG_FMR1": "1",
    "PRODG_CMP": "1",
    "PRODG_STORE": "2",
}

# Macros the GCC 2.95.3 driver defines for g++ on powerpc-eabi with
# -mcpu=750 (from gcc/config/rs6000/sysv4.h, eabi.h and gcc.c). The host
# preprocessor runs with -undef, so none of its own (x86, 64-bit) macros
# leak in. Whether ProDG's driver adds more of its own is unknown.
TARGET_MACROS = [
    "__GNUC__=2",
    "__GNUC_MINOR__=95",
    "__GNUG__=2",
    "PPC",
    "__PPC__",
    "__PPC",
    "__embedded__",
    "_ARCH_PPC",
    "_CALL_SYSV",
    "_BIG_ENDIAN",
    "__BIG_ENDIAN__",
    "__CHAR_UNSIGNED__",
]

AS_FLAGS = ["-mbig", "-mregnames", "-many"]


class CompileError(Exception):
    pass


def default_version() -> Tuple[str, int]:
    """The default game version and its index, as configure.py defines them."""
    text = (ROOT / "configure.py").read_text()
    m = re.search(r"VERSIONS\s*=\s*\[(.*?)\]", text, re.S)
    versions = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    d = re.search(r"DEFAULT_VERSION\s*=\s*(\d+)", text)
    if not versions:
        return "G3BE9G", 0
    idx = int(d.group(1)) if d else 0
    return versions[idx], idx


def version_index(version: str) -> int:
    text = (ROOT / "configure.py").read_text()
    m = re.search(r"VERSIONS\s*=\s*\[(.*?)\]", text, re.S)
    versions = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    if version not in versions:
        raise CompileError(f"unknown version {version} (configure.py has {', '.join(versions)})")
    return versions.index(version)


def default_cflags(version: str) -> List[str]:
    """Mirror of cflags_game in configure.py (release build)."""
    return [
        "-O2",
        "-I",
        "include",
        "-I",
        f"build/{version}/include",
        f"-DBUILD_VERSION={version_index(version)}",
        f"-DVERSION_{version}",
        "-DNDEBUG=1",
    ]


def ninja_cflags(ninja: Path, src_rel: str) -> Optional[List[str]]:
    """The cflags build.ninja uses for this source with the prodg_cc rule, or
    None if it isn't a prodg_cc unit."""
    text = ninja.read_text()
    text = re.sub(r" \$\n\s*", " ", text)  # join continuation lines
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"build (\S+): (\S+) (.*)$", line)
        if not m or m.group(2) != "prodg_cc":
            continue
        inputs = m.group(3).split("|")[0].split()
        if src_rel not in inputs:
            continue
        for var in lines[i + 1 :]:
            if not var.startswith("  "):
                break
            vm = re.match(r"\s+cflags = (.*)$", var)
            if vm:
                return shlex.split(vm.group(1).replace("$$", "$"))
        raise CompileError(f"{ninja} builds {src_rel} with prodg_cc but has no cflags for it; rerun python configure.py")
    return None


def split_cflags(cflags: List[str]) -> Tuple[List[str], List[str]]:
    """Split driver flags into preprocessor flags and cc1plus flags."""
    cpp: List[str] = []
    cc1: List[str] = []
    i = 0
    while i < len(cflags):
        flag = cflags[i]
        if flag in ("-I", "-D", "-U", "-include"):
            if i + 1 >= len(cflags):
                raise CompileError(f"{flag} without an argument in cflags")
            cpp += [flag, cflags[i + 1]]
            i += 2
            continue
        if flag.startswith(("-I", "-D", "-U")):
            cpp.append(flag)
        elif flag.startswith(("-O", "-f", "-m", "-W", "-w")) or flag in ("-g", "-pedantic", "-ansi"):
            cc1.append(flag)
            if flag.startswith("-O") and flag != "-O0":
                cpp.append("-D__OPTIMIZE__")
        elif flag in ("-c",):
            pass
        else:
            print(f"compile.py: warning: ignoring flag {flag}", file=sys.stderr)
        i += 1
    return cpp, cc1


def find_preprocessor(requested: Optional[str]) -> List[str]:
    if requested:
        return shlex.split(requested)
    for name in ("gcc", "clang", "cc"):
        if shutil.which(name):
            return [name]
    raise CompileError("no host C preprocessor found (need gcc or clang on PATH, or pass --cpp)")


def run(cmd: List[str], cwd: Path, env: Optional[Dict[str, str]], verbose: bool, what: str) -> None:
    if verbose:
        print("+ " + " ".join(shlex.quote(c) for c in cmd), file=sys.stderr)
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env)
    except FileNotFoundError:
        raise CompileError(f"{what}: {cmd[0]} not found")
    if proc.returncode != 0:
        raise CompileError(f"{what} failed (exit {proc.returncode})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile a C++ file with the ProDG stand-in compiler.")
    parser.add_argument("source", type=Path, help="C++ source file")
    parser.add_argument("-o", "--output", type=Path, help="output object (default: build/standin/obj/<source>.o)")
    parser.add_argument("-S", dest="asm_only", action="store_true", help="stop after cc1plus and write assembly to the output path")
    parser.add_argument("--keep", action="store_true", help="keep the .ii and .s files next to the output")
    parser.add_argument("--version", help="game version for the -I/-D flags (default: configure.py's default)")
    parser.add_argument("--standin", type=Path, default=ROOT / "build" / "standin", help="build.py output directory (default: build/standin)")
    parser.add_argument("--binutils", type=Path, default=ROOT / "build" / "binutils", help="powerpc-eabi binutils directory (default: build/binutils)")
    parser.add_argument("--cpp", help="host preprocessor command (default: gcc, else clang)")
    parser.add_argument("--no-ninja-flags", action="store_true", help="don't read the unit's cflags from build.ninja; use configure.py's defaults")
    parser.add_argument("--cc1", dest="cc1_extra", action="append", default=[], metavar="FLAG", help="extra cc1plus flag (repeatable), e.g. --cc1=-fno-schedule-insns2")
    parser.add_argument("--env", action="append", default=[], metavar="NAME=VALUE", help="set (or with an empty value, unset) an environment variable for cc1plus")
    parser.add_argument("-v", "--verbose", action="store_true", help="print the commands")
    args = parser.parse_args()

    try:
        src = args.source.resolve()
        if not src.is_file():
            raise CompileError(f"{args.source} not found")
        if src.suffix.lower() not in (".cpp", ".cc", ".cxx", ".cp", ".c++"):
            raise CompileError("the stand-in only has cc1plus, so it compiles C++ files only")
        try:
            src_rel = src.relative_to(ROOT).as_posix()
        except ValueError:
            src_rel = None

        cc1plus = args.standin.resolve() / f"cc1plus{EXE}"
        if not cc1plus.is_file():
            raise CompileError(f"{cc1plus} not found; run python tools/standin/build.py first")
        gas = args.binutils.resolve() / f"powerpc-eabi-as{EXE}"
        if not args.asm_only and not gas.is_file():
            raise CompileError(f"{gas} not found; run python tools/standin/build.py (or configure.py and ninja) first")

        version = args.version.upper() if args.version else default_version()[0]
        cflags = None
        ninja = ROOT / "build.ninja"
        if ninja.is_file() and not args.no_ninja_flags and not args.version:
            cflags = ninja_cflags(ninja, src_rel) if src_rel else None
            if cflags is None:
                print(
                    f"compile.py: warning: {args.source} is not a prodg_cc unit in build.ninja; "
                    "using the default flags (cflags_game in configure.py)",
                    file=sys.stderr,
                )
        flag_source = "build.ninja"
        if cflags is None:
            cflags = default_cflags(version)
            flag_source = "configure.py defaults"
        cpp_flags, cc1_flags = split_cflags(cflags)
        if args.verbose:
            print(f"compile.py: flags from {flag_source}: {' '.join(cflags)}", file=sys.stderr)

        if args.output:
            output = args.output.resolve()
        else:
            stem = Path(src_rel).with_suffix("") if src_rel else Path(src.stem)
            output = (args.standin.resolve() / "obj" / stem).with_suffix(".s" if args.asm_only else ".o")
        output.parent.mkdir(parents=True, exist_ok=True)

        env = dict(os.environ)
        # Only compile.py's own values and --env reach the patched cc1plus.
        passed = {item.partition("=")[0] for item in args.env}
        inherited = sorted(name for name in env if name.startswith("PRODG_") and name not in passed)
        if inherited:
            print(
                f"compile.py: warning: ignoring {', '.join(inherited)} from the environment; set PRODG_* variables with --env",
                file=sys.stderr,
            )
            for name in inherited:
                del env[name]
        env.update(PRODG_ENV)
        for item in args.env:
            name, _, value = item.partition("=")
            if value:
                env[name] = value
            else:
                env.pop(name, None)

        with tempfile.TemporaryDirectory(prefix="standin-") as tmp:
            base = output.with_suffix("") if args.keep else Path(tmp) / output.stem
            ii = base.with_suffix(".ii")
            asm = output if args.asm_only else base.with_suffix(".s")

            # No -P: the line markers make cc1plus report errors against the
            # real source files and lines.
            cpp_cmd = find_preprocessor(args.cpp) + ["-E", "-x", "c++", "-nostdinc", "-undef", "-std=gnu++98"]
            cpp_cmd += ["-D" + m for m in TARGET_MACROS]
            cpp_cmd += cpp_flags + [str(src), "-o", str(ii)]
            run(cpp_cmd, ROOT, None, args.verbose, "preprocessing")

            cc1_cmd = [str(cc1plus), "-quiet"] + cc1_flags + CC1PLUS_FLAGS + args.cc1_extra + [str(ii), "-o", str(asm)]
            run(cc1_cmd, ROOT, env, args.verbose, "cc1plus")

            if not args.asm_only:
                run([str(gas)] + AS_FLAGS + [str(asm), "-o", str(output)], ROOT, None, args.verbose, "powerpc-eabi-as")
    except CompileError as e:
        sys.exit(f"compile.py: error: {e}")


if __name__ == "__main__":
    main()
