#!/usr/bin/env python3

###
# Builds the ProDG stand-in compiler: upstream GCC 2.95.3 cc1plus for
# powerpc-eabi with tools/standin/prodg-standin.patch applied.
#
# Usage:
#   python tools/standin/build.py
#
# Steps (each is skipped when already done, so the script can be rerun):
#   1. download the files in tools/standin/files.txt from the gcc-mirror
#      repository on GitHub into build/standin/src, checking each against
#      the sha256 in files.txt
#   2. apply tools/standin/prodg-standin.patch, and apply it again to any
#      patched file that went missing or changed since
#   3. configure and build cc1plus as a 32-bit x86 Linux program
#      (build/standin/gcc), then copy it to build/standin/cc1plus
#   4. download the powerpc-eabi binutils the same way configure.py does
#      (tools/download_tool.py, into build/binutils)
#
# Needs Linux on x86-64 (or x86) with make and a gcc that can build 32-bit
# programs (Debian/Ubuntu: apt install gcc-multilib).
# See tools/standin/README.md.
###

import argparse
import concurrent.futures
import hashlib
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent

GCC_TAG = "releases/gcc-2.95.3"
GCC_URL = f"https://raw.githubusercontent.com/gcc-mirror/gcc/{GCC_TAG}/"

# How the host compiler builds GCC 2.95.3. 2.95 assumes 32-bit longs and
# pointers, hence -m32. -std=gnu89 and -fcommon keep the old C (K&R
# definitions, tentative definitions shared between files) building with a
# modern gcc. _FORTIFY_SOURCE and the stack protector are off because the
# old code trips them at run time ("buffer overflow detected").
HOST_CC = "gcc -m32"
HOST_CFLAGS = [
    "-O1",
    "-g",
    "-w",
    "-std=gnu89",
    "-fcommon",
    "-fno-strict-aliasing",
    "-U_FORTIFY_SOURCE",
    "-D_FORTIFY_SOURCE=0",
    "-fno-stack-protector",
]

CONFIGURE_ARGS = [
    "--host=i686-pc-linux-gnu",
    "--build=i686-pc-linux-gnu",
    "--target=powerpc-eabi",
    "--disable-nls",
    "--enable-languages=c++",
    "--with-gnu-as",
    "--with-gnu-ld",
]

# Files that GCC's makefiles can regenerate from other sources, in the
# order they depend on each other. The upstream copies are used as they are:
# after download every source gets the same old timestamp and these get
# newer ones, so make never tries to run autoconf, autoheader, bison or
# gperf (which may be missing or too new).
GENERATED = [
    "gcc/configure",
    "gcc/cstamp-h.in",
    "gcc/config.in",
    "gcc/c-parse.y",
    "gcc/c-parse.c",
    "gcc/c-parse.h",
    "gcc/c-gperf.h",
    "gcc/cexp.c",
    "gcc/cp/hash.h",
    "gcc/cp/parse.c",
    "gcc/cp/parse.h",
]
# 2001-03-16, the GCC 2.95.3 release date.
SOURCE_MTIME = 984700800

# Programs make would only run if the timestamps above were wrong.
SHIMMED_TOOLS = ["autoconf", "autoheader", "bison", "yacc", "gperf", "makeinfo"]

# Bump when the configure/make steps change, to force a rebuild.
BUILD_RECIPE_VERSION = "1"


class BuildError(Exception):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


def read_list(path: Path) -> Dict[str, str]:
    """files.txt as {path: sha256 of the pristine upstream file}."""
    files = {}
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            raise BuildError(f"{path}: expected '<sha256>  <path>', got: {line}")
        files[parts[1]] = parts[0]
    return files


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> Optional[str]:
    """The file's sha256, or None if it doesn't exist."""
    try:
        return sha256_bytes(path.read_bytes())
    except FileNotFoundError:
        return None


###
# Download
###


def fetch_one(rel: str, sha: str, dest_root: Path, retries: int) -> Tuple[str, Optional[str]]:
    dest = dest_root / rel
    if dest.is_file() and dest.stat().st_size > 0:
        return rel, None
    url = GCC_URL + rel
    last_err = "unknown error"
    for attempt in range(retries):
        if attempt:
            time.sleep(min(2**attempt, 10))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as response:
                data = response.read()
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 404:
                break
            continue
        except Exception as e:  # network errors, timeouts
            last_err = str(e)
            continue
        if not data:
            last_err = "empty response"
            continue
        if sha256_bytes(data) != sha:
            # Nothing is saved, so a rerun downloads the file again.
            last_err = f"sha256 is {sha256_bytes(data)}, files.txt says {sha}; the download was not kept"
            break
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
        return rel, None
    return rel, f"{url}: {last_err}"


def download_sources(files: Dict[str, str], src: Path, jobs: int, retries: int) -> None:
    missing = [f for f in files if not ((src / f).is_file() and (src / f).stat().st_size > 0)]
    if not missing:
        log(f"Sources: all {len(files)} files present in {src}")
        return
    log(f"Sources: downloading {len(missing)} of {len(files)} files from {GCC_URL}")
    errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for rel, err in pool.map(lambda f: fetch_one(f, files[f], src, retries), missing):
            if err:
                errors.append(err)
    if errors:
        msg = "\n  ".join(errors)
        raise BuildError(
            f"could not download {len(errors)} file(s):\n  {msg}\n"
            "Rerun to retry; files that were downloaded are kept."
        )


def verify_sources(files: Dict[str, str], src: Path) -> None:
    """Check that the files are the pristine upstream ones; delete those that aren't."""
    bad = [rel for rel, sha in files.items() if sha256_file(src / rel) != sha]
    if bad:
        for rel in bad:
            (src / rel).unlink(missing_ok=True)
        msg = "\n  ".join(bad)
        raise BuildError(
            f"{len(bad)} file(s) in {src} did not match the sha256 in files.txt, so they were deleted:\n  {msg}\n"
            "Rerun to download them again."
        )


###
# Patch (a small unified diff applier, so `patch` isn't needed)
###

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def split_lines(text: str) -> List[str]:
    """Split after each "\\n" only, keeping it. str.splitlines() also splits
    on form feeds and other separators, and GCC's sources have form feed lines."""
    lines = [line + "\n" for line in text.split("\n")]
    lines[-1] = lines[-1][:-1]
    if not lines[-1]:
        lines.pop()
    return lines


def parse_patch(text: str) -> List[Tuple[str, List[Tuple[int, List[Tuple[str, str]]]]]]:
    lines = split_lines(text)
    result = []
    i = 0
    while i < len(lines):
        if not (lines[i].startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ ")):
            i += 1
            continue
        path = lines[i + 1][4:].split("\t")[0].strip()
        if path.startswith("b/"):
            path = path[2:]
        i += 2
        hunks = []
        while i < len(lines) and lines[i].startswith("@@"):
            m = HUNK_RE.match(lines[i])
            if not m:
                raise BuildError(f"bad hunk header in patch: {lines[i].rstrip()}")
            old_start = int(m.group(1))
            old_len = int(m.group(2)) if m.group(2) is not None else 1
            new_len = int(m.group(4)) if m.group(4) is not None else 1
            i += 1
            body = []
            n_old = n_new = 0
            while n_old < old_len or n_new < new_len:
                if i >= len(lines):
                    raise BuildError(f"truncated hunk for {path} in patch")
                line = lines[i]
                i += 1
                if line.startswith("\\"):
                    continue
                tag, content = line[:1], line[1:]
                if tag == " ":
                    n_old += 1
                    n_new += 1
                elif tag == "-":
                    n_old += 1
                elif tag == "+":
                    n_new += 1
                elif line in ("\n", "\r\n"):
                    # Blank context line whose leading space was stripped.
                    tag, content = " ", line
                    n_old += 1
                    n_new += 1
                else:
                    raise BuildError(f"bad line in patch hunk for {path}: {line.rstrip()}")
                body.append((tag, content))
            while i < len(lines) and lines[i].startswith("\\"):
                i += 1
            hunks.append((old_start, body))
        result.append((path, hunks))
    headers = sum(1 for line in lines if line.startswith("@@"))
    parsed = sum(len(hunks) for _, hunks in result)
    if parsed != headers:
        raise BuildError(f"patch has {headers} hunk headers, but only {parsed} hunks could be read")
    return result


def apply_patch(patch_text: str, src: Path, check_only: bool = False, only: Optional[Set[str]] = None) -> List[str]:
    """Apply the patch to the files in src (or only to those in `only`)."""
    patched = []
    for rel, hunks in parse_patch(patch_text):
        if only is not None and rel not in only:
            continue
        target = src / rel
        if not target.is_file():
            raise BuildError(f"patch: {rel} is not in {src} (add it to files.txt)")
        lines = split_lines(target.read_text(encoding="latin-1"))
        offset = 0
        for n, (old_start, body) in enumerate(hunks, 1):
            old = [c for t, c in body if t in " -"]
            new = [c for t, c in body if t in " +"]
            want = old_start - 1 + offset
            pos = None
            for delta in range(0, 200):
                for cand in (want - delta, want + delta):
                    if 0 <= cand <= len(lines) - len(old) and lines[cand : cand + len(old)] == old:
                        pos = cand
                        break
                if pos is not None:
                    break
            if pos is None:
                raise BuildError(
                    f"patch: hunk {n} of {rel} does not apply (expected near line {old_start}), "
                    f"so {target} is not the pristine upstream file. Delete it and rerun; "
                    "build.py downloads it again."
                )
            lines[pos : pos + len(old)] = new
            offset += len(new) - len(old)
        if not check_only:
            target.write_text("".join(lines), encoding="latin-1")
        patched.append(rel)
    return patched


def read_patch_stamp(stamp: Path) -> Tuple[str, Dict[str, str]]:
    """The hash of the applied patch and {patched file: its sha256 after patching}."""
    if not stamp.is_file():
        return "", {}
    lines = stamp.read_text().splitlines()
    patched = {}
    for line in lines[1:]:
        parts = line.split()
        if len(parts) == 2:
            patched[parts[1]] = parts[0]
        elif parts:
            patched[parts[0]] = ""  # stamp from an older build.py: no hash, so patch again
    return (lines[0].strip() if lines else ""), patched


def patch_sources(patch_path: Path, src: Path, files: Dict[str, str], jobs: int, retries: int) -> Tuple[str, bool]:
    """Apply the patch where needed. Returns its hash and whether any file was patched."""
    patch_bytes = patch_path.read_bytes()
    patch_hash = sha256_bytes(patch_bytes)
    stamp = src / ".standin-patch"
    old_hash, old_patched = read_patch_stamp(stamp)
    # Every file the patch hasn't changed must be the upstream one.
    verify_sources({rel: sha for rel, sha in files.items() if rel not in old_patched}, src)
    if old_hash == patch_hash:
        stale = [rel for rel, sha in old_patched.items() if sha256_file(src / rel) != sha]
        if not stale:
            log(f"Patch: already applied ({patch_path.name})")
            return patch_hash, False
        # Changed since it was patched, or deleted (and so downloaded again
        # unpatched by download_sources).
        log(f"Patch: {', '.join(stale)} deleted or changed since patching, restoring pristine copies")
    else:
        # A different patch was applied before: get pristine copies back.
        stale = list(old_patched)
        if stale:
            log("Patch: patch changed, restoring pristine copies of the previously patched files")
    for rel in stale:
        if sha256_file(src / rel) != files.get(rel):
            (src / rel).unlink(missing_ok=True)
    done = {rel: sha for rel, sha in old_patched.items() if rel not in stale}
    stamp.unlink(missing_ok=True)
    if stale:
        download_sources(files, src, jobs, retries)
    patch_text = patch_bytes.decode("latin-1").replace("\r\n", "\n")
    todo = {rel for rel, _ in parse_patch(patch_text)} - set(done)
    verify_sources({rel: files[rel] for rel in todo if rel in files}, src)
    # Check every hunk first so a failure leaves the tree untouched.
    apply_patch(patch_text, src, check_only=True, only=todo)
    patched = apply_patch(patch_text, src, only=todo)
    done.update((rel, sha256_file(src / rel)) for rel in patched)
    stamp.write_text(patch_hash + "\n" + "".join(f"{sha}  {rel}\n" for rel, sha in sorted(done.items())))
    log(f"Patch: applied {patch_path.name} to {len(patched)} file(s)")
    return patch_hash, True


def set_source_times(src: Path) -> None:
    for path in src.rglob("*"):
        if path.is_file() and not path.name.startswith(".standin"):
            os.utime(path, (SOURCE_MTIME, SOURCE_MTIME))
    for n, rel in enumerate(GENERATED, 1):
        path = src / rel
        if path.is_file():
            t = SOURCE_MTIME + 60 * n
            os.utime(path, (t, t))


def make_scripts_executable(src: Path) -> None:
    for path in src.rglob("*"):
        if not path.is_file() or path.suffix in (".c", ".h", ".md", ".def", ".in", ".y"):
            continue
        with open(path, "rb") as f:
            is_script = f.read(2) == b"#!"
        if is_script or path.name in ("configure.frag", "move-if-change"):
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


###
# Host checks
###


def run_logged(cmd: List[str], cwd: Path, env: Dict[str, str], logfile: Path, what: str) -> None:
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with open(logfile, "w") as f:
        f.write("$ " + " ".join(cmd) + "\n")
        f.flush()
        rc = subprocess.call(cmd, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT)
    if rc != 0:
        tail = logfile.read_text(errors="replace").splitlines()[-25:]
        raise BuildError(f"{what} failed (exit {rc}). Last lines of {logfile}:\n    " + "\n    ".join(tail))


def check_host(cc: str, work: Path) -> List[str]:
    if platform.system() != "Linux":
        raise BuildError(
            f"building the stand-in needs Linux (this is {platform.system()}). "
            "On Windows use WSL; compile.py and compare.py can then use the result."
        )
    if platform.machine().lower() not in ("x86_64", "amd64", "i386", "i486", "i586", "i686"):
        log(f"Warning: untested host architecture {platform.machine()}; GCC 2.95 needs a 32-bit x86 build.")
    for tool in ("sh", "make", cc.split()[0]):
        if shutil.which(tool) is None:
            raise BuildError(f"'{tool}' not found on PATH")
    work.mkdir(parents=True, exist_ok=True)
    test_c = work / "m32test.c"
    test_c.write_text("#include <stdio.h>\n#include <stdlib.h>\nint main(void) { printf(\"%d\\n\", (int) sizeof(long)); return 0; }\n")
    exe = work / "m32test"
    cmd = cc.split() + ["-o", str(exe), str(test_c)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise BuildError(
            f"'{cc}' cannot build a 32-bit program:\n{proc.stderr.strip()}\n"
            "Install 32-bit build support (Debian/Ubuntu: sudo apt install gcc-multilib; "
            "Fedora: sudo dnf install glibc-devel.i686 libgcc.i686)."
        )
    out = subprocess.run([str(exe)], capture_output=True, text=True).stdout.strip()
    if out != "4":
        raise BuildError(f"'{cc}' does not produce 32-bit programs (sizeof(long) = {out})")
    # GCC 14 and later turn some old-C warnings into errors; -fpermissive
    # turns them back into warnings. Older gcc rejects it for C.
    extra = []
    proc = subprocess.run(
        cc.split() + ["-fpermissive", "-Werror", "-c", "-o", str(work / "m32test.o"), str(test_c)],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        extra.append("-fpermissive")
    return extra


def write_shims(shim_dir: Path) -> None:
    shim_dir.mkdir(parents=True, exist_ok=True)
    for tool in SHIMMED_TOOLS:
        path = shim_dir / tool
        path.write_text(
            "#!/bin/sh\n"
            f'echo "standin build: make tried to run {tool} $*." >&2\n'
            'echo "That only happens when the GCC source timestamps are off;" >&2\n'
            'echo "rerun tools/standin/build.py --force, which resets them." >&2\n'
            "exit 1\n"
        )
        path.chmod(0o755)


###
# Build
###


def build_cc1plus(src: Path, out: Path, cc: str, jobs: int, extra_cflags: List[str], stamp_value: str) -> None:
    final = out / "cc1plus"
    stamp = out / ".standin-build"
    if final.is_file() and stamp.is_file() and stamp.read_text().strip() == stamp_value:
        log(f"cc1plus: up to date ({final})")
        return

    build = out / "gcc"
    logs = out / "logs"
    if build.exists():
        log(f"cc1plus: removing old build directory {build}")
        shutil.rmtree(build)
    stamp.unlink(missing_ok=True)
    final.unlink(missing_ok=True)
    build.mkdir(parents=True)

    make_scripts_executable(src)
    set_source_times(src)
    shims = out / "shims"
    write_shims(shims)

    cflags = " ".join(HOST_CFLAGS + extra_cflags)
    env = dict(os.environ)
    env["PATH"] = str(shims) + os.pathsep + env.get("PATH", "")
    env["CC"] = cc
    env["CFLAGS"] = cflags
    env["LC_ALL"] = "C"
    env["CONFIG_SHELL"] = "/bin/sh"
    for var in ("CPPFLAGS", "LDFLAGS", "LIBS", "MAKEFLAGS", "MFLAGS", "GCC_EXEC_PREFIX", "LIBRARY_PATH"):
        env.pop(var, None)

    log(f"cc1plus: configuring in {build}")
    configure = src / "gcc" / "configure"
    run_logged(["/bin/sh", str(configure)] + CONFIGURE_ARGS, build, env, logs / "configure.log", "configure")
    for name in ("Makefile", "config.status", "auto-host.h", "tm.h", "options.h", "specs.h"):
        if not (build / name).is_file():
            raise BuildError(f"configure did not create {name}; see {logs / 'configure.log'}")
    # configure fills options.h/specs.h from the language directories; an
    # empty one means cc1plus would reject C++ options like -fno-rtti.
    if "cp/lang-options.h" not in (build / "options.h").read_text():
        raise BuildError(f"{build / 'options.h'} does not include cp/lang-options.h; is gcc/cp/lang-options.h in files.txt?")

    log(f"cc1plus: building with {jobs} job(s) (takes a minute or two; log in {logs / 'make.log'})")
    make_args = ["cc1plus", f"CC={cc}", f"HOST_CC={cc}", f"CFLAGS={cflags}"]
    try:
        run_logged(["make", f"-j{jobs}"] + make_args, build, env, logs / "make.log", "make cc1plus")
    except BuildError:
        if jobs == 1:
            raise
        # GCC 2.95's makefiles predate parallel builds; finish serially
        # before giving up.
        log("cc1plus: parallel make failed, continuing with -j1")
        run_logged(["make", "-j1"] + make_args, build, env, logs / "make-j1.log", "make cc1plus")
    built = build / "cc1plus"
    if not built.is_file():
        raise BuildError(f"make finished but {built} is missing; see {logs / 'make.log'}")
    shutil.copy2(built, final)
    stamp.write_text(stamp_value + "\n")
    log(f"cc1plus: built {final}")


def configured_binutils_tag() -> str:
    text = (ROOT / "configure.py").read_text()
    m = re.search(r'binutils_tag\s*=\s*"([^"]+)"', text)
    if not m:
        raise BuildError("could not find config.binutils_tag in configure.py")
    return m.group(1)


def fetch_binutils(dest: Path) -> None:
    exe = ".exe" if platform.system() == "Windows" else ""
    if (dest / f"powerpc-eabi-as{exe}").is_file() and (dest / f"powerpc-eabi-objdump{exe}").is_file():
        log(f"binutils: present in {dest}")
        return
    tag = configured_binutils_tag()
    log(f"binutils: downloading gc-wii-binutils {tag} into {dest}")
    cmd = [sys.executable, str(ROOT / "tools" / "download_tool.py"), "binutils", str(dest), "--tag", tag]
    if subprocess.call(cmd) != 0 or not (dest / f"powerpc-eabi-as{exe}").is_file():
        raise BuildError(f"downloading binutils failed (command: {' '.join(cmd)})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the GCC 2.95.3 ProDG stand-in compiler.")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "standin", help="output directory (default: build/standin)")
    parser.add_argument("--binutils", type=Path, default=ROOT / "build" / "binutils", help="where to put the powerpc-eabi binutils (default: build/binutils, shared with configure.py)")
    parser.add_argument("--files", type=Path, default=SCRIPT_DIR / "files.txt", help="list of GCC source files")
    parser.add_argument("--patch", type=Path, default=SCRIPT_DIR / "prodg-standin.patch", help="patch to apply")
    parser.add_argument("--cc", default=HOST_CC, help=f"host C compiler for 32-bit code (default: '{HOST_CC}')")
    parser.add_argument("-j", "--jobs", type=int, default=min(os.cpu_count() or 2, 16), help="parallel make jobs")
    parser.add_argument("--retries", type=int, default=4, help="download attempts per file")
    parser.add_argument("--force", action="store_true", help="rebuild cc1plus even if it is up to date")
    parser.add_argument("--no-binutils", action="store_true", help="don't download binutils")
    args = parser.parse_args()

    start = time.time()
    out = args.out.resolve()
    src = out / "src"
    try:
        if " " in str(out):
            raise BuildError(f"the output path must not contain spaces (GCC's makefiles can't handle it): {out}")
        files = read_list(args.files)
        extra_cflags = check_host(args.cc, out / "tmp")
        download_sources(files, src, jobs=8, retries=args.retries)
        patch_hash, repatched = patch_sources(args.patch, src, files, jobs=8, retries=args.retries)
        stamp_value = sha256_bytes(
            "\n".join(
                [BUILD_RECIPE_VERSION, patch_hash, args.cc, " ".join(HOST_CFLAGS + extra_cflags)]
                + [f"{sha}  {rel}" for rel, sha in files.items()]
            ).encode()
        )
        if args.force or repatched:
            (out / ".standin-build").unlink(missing_ok=True)
        build_cc1plus(src, out, args.cc, args.jobs, extra_cflags, stamp_value)
        if not args.no_binutils:
            fetch_binutils(args.binutils.resolve())
    except BuildError as e:
        sys.exit(f"build.py: error: {e}")
    log(f"Done in {time.time() - start:.0f}s. Compile with: python tools/standin/compile.py <file.cpp>")


if __name__ == "__main__":
    main()
