#!/usr/bin/env python3

###
# Finds certain source-file boundaries in the game code of a ProDG (GCC 2.95)
# DOL and prints them as splits.txt entries, with string hints for each group.
#
# GCC emits a translation unit's static constructor (`_GLOBAL_$I$...`) as its
# last function, followed by the static destructor (`_GLOBAL_$D$...`) when there
# is one. The entries of the .ctors/.dtors tables therefore mark the end of a
# source file. Each group between two markers holds one or more whole files.
#
# Usage:
#   python3 tools/tu_groups.py orig/G3BE9G/sys/main.dol config/G3BE9G/symbols.txt
###

import argparse
import collections
import re
import struct
from typing import Dict, Iterator, List, Optional, Tuple

SDA_BASE = 0x802E1BA0
CTORS_DTORS = 0x801E0D40  # merged .ctors/.dtors DOL section
GAME_TEXT = (0x800034A0, 0x8017BF88)
CLASS_NAME = re.compile(r"\b([cC][A-Z][A-Za-z0-9_]+)::")


class Dol:
    def __init__(self, path: str) -> None:
        with open(path, "rb") as f:
            self.data = f.read()
        self.offsets = struct.unpack_from(">18I", self.data, 0x00)
        self.addresses = struct.unpack_from(">18I", self.data, 0x48)
        self.sizes = struct.unpack_from(">18I", self.data, 0x90)

    def _pos(self, addr: int) -> Optional[int]:
        for off, start, size in zip(self.offsets, self.addresses, self.sizes):
            if size and start <= addr < start + size:
                return off + addr - start
        return None

    def word(self, addr: int) -> int:
        pos = self._pos(addr)
        assert pos is not None
        return struct.unpack_from(">I", self.data, pos)[0]

    def string(self, addr: int, min_len: int = 4) -> Optional[str]:
        pos = self._pos(addr)
        if pos is None:
            return None
        end = self.data.find(b"\0", pos, pos + 256)
        raw = self.data[pos:end]
        if end < 0 or len(raw) < min_len or not all(32 <= c < 127 or c in (9, 10) for c in raw):
            return None
        return raw.decode("ascii")


def load_functions(path: str) -> List[Tuple[int, int]]:
    pattern = re.compile(r"\S+ = \.text:0x([0-9A-F]+); // type:function size:0x([0-9A-F]+)")
    functions = []
    with open(path) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                functions.append((int(m.group(1), 16), int(m.group(2), 16)))
    return sorted(functions)


def s16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def address_refs(dol: Dol, start: int, size: int) -> Iterator[int]:
    """Addresses formed with `lis` + `addi`/`ori`, or relative to r13."""
    hi: Dict[int, int] = {}
    for pc in range(start, start + size, 4):
        ins = dol.word(pc)
        op, rd, ra, imm = ins >> 26, (ins >> 21) & 31, (ins >> 16) & 31, ins & 0xFFFF
        if op == 15 and ra == 0:  # lis rD, hi
            hi[rd] = imm << 16
            continue
        if op == 14 and ra in hi:  # addi rD, rA, lo
            yield (hi[ra] + s16(imm)) & 0xFFFFFFFF
        elif op == 24 and rd in hi:  # ori rA, rS, lo
            yield hi[rd] | imm
        elif op == 14 and ra == 13:
            yield (SDA_BASE + s16(imm)) & 0xFFFFFFFF
        # Forget a register once something else writes it.
        if op in (14, 15, 32, 34, 40, 42):
            hi.pop(rd, None)
        elif op in (21, 24, 28):
            hi.pop(ra, None)
        elif op == 31:
            hi.pop(rd, None)
            hi.pop(ra, None)


def find_groups(dol: Dol, functions: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    words = struct.unpack_from(">152I", dol.data, dol._pos(CTORS_DTORS) or 0)
    # Both tables start with -1 and end with 0.
    split = words.index(0xFFFFFFFF, 1)
    ctors = {w for w in words[1:split] if w not in (0, 0xFFFFFFFF)}
    dtors = {w for w in words[split + 1 :] if w not in (0, 0xFFFFFFFF)}

    game = [f for f in functions if GAME_TEXT[0] <= f[0] < GAME_TEXT[1]]
    index = {addr: i for i, (addr, _) in enumerate(game)}
    ends = []
    for ctor in sorted(ctors):
        i = index.get(ctor)
        if i is None:
            continue
        if i + 1 < len(game) and game[i + 1][0] in dtors:
            i += 1
        ends.append(i)
    if not ends or ends[-1] != len(game) - 1:
        ends.append(len(game) - 1)

    groups = []
    first = 0
    for last in ends:
        groups.append((game[first][0], game[last][0] + game[last][1]))
        first = last + 1
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description="Print ctor-delimited source-file groups.")
    parser.add_argument("dol", help="original main.dol")
    parser.add_argument("symbols", help="symbols.txt")
    args = parser.parse_args()

    dol = Dol(args.dol)
    functions = load_functions(args.symbols)
    for start, end in find_groups(dol, functions):
        classes: collections.Counter = collections.Counter()
        strings = []
        for addr, size in functions:
            if start <= addr < end:
                for ref in address_refs(dol, addr, size):
                    text = dol.string(ref)
                    if text:
                        classes.update(m.group(1) for m in CLASS_NAME.finditer(text))
                        strings.append(text.replace("\n", " ").strip()[:30])
        hints = [name for name, _ in classes.most_common(3)] or strings[:3] or ["no strings"]
        print(f"// {', '.join(hints)}")
        print(f"game/group_{start:08X}.cpp:")
        print(f"\t.text       start:0x{start:08X} end:0x{end:08X}")
        print()


if __name__ == "__main__":
    main()
