#!/usr/bin/env python3

###
# Converts the linked ELF to a DOL, then rewrites small-data accesses to
# follow SN Systems ProDG's convention.
#
# ProDG addresses .sdata, .sbss and .sdata2 all through r13 (_SDA_BASE_).
# mwld follows the EABI instead and resolves SDA21 relocations into .sdata2
# against r2 (_SDA2_BASE_). After elf2dol, every D-form instruction based on
# r2 whose effective address falls inside .sdata2 is rewritten to use r13
# with the matching offset. The original game never uses r2 as a base
# register, so nothing else is touched.
#
# Usage:
#   python3 tools/sn_elf2dol.py <dtk> <in.elf> <out.dol>
###

import argparse
import struct
import subprocess
import sys
from typing import Dict, Tuple

# D-form loads, stores and addi (opcode 14). Update forms (lwzu etc.) are left
# out on purpose: they write the base register back, so they can't be SDA21.
D_FORM_OPCODES = {
    14,  # addi
    32,  # lwz
    34,  # lbz
    36,  # stw
    38,  # stb
    40,  # lhz
    42,  # lha
    44,  # sth
    46,  # lmw
    47,  # stmw
    48,  # lfs
    50,  # lfd
    52,  # stfs
    54,  # stfd
}

DOL_TEXT_SECTIONS = 7
DOL_SECTIONS = 18


def read_elf_info(path: str) -> Tuple[Dict[str, int], Tuple[int, int]]:
    """Returns the linker symbols we need and the .sdata2 address range."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 2:
        sys.exit(f"{path}: not a 32-bit big-endian ELF")

    e_shoff = struct.unpack_from(">I", data, 0x20)[0]
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from(">HHH", data, 0x2E)

    sections = []
    for i in range(e_shnum):
        sections.append(
            struct.unpack_from(">IIIIIIIIII", data, e_shoff + i * e_shentsize)
        )

    def section_name(index: int) -> str:
        shstr_offset = sections[e_shstrndx][4]
        start = shstr_offset + sections[index][0]
        return data[start : data.index(b"\0", start)].decode("ascii")

    sdata = None
    sdata2 = None
    symbols: Dict[str, int] = {}
    for i, (_, sh_type, _, sh_addr, sh_offset, sh_size, sh_link, _, _, sh_entsize) in enumerate(
        sections
    ):
        if section_name(i) == ".sdata":
            sdata = sh_addr
        elif section_name(i) == ".sdata2":
            sdata2 = (sh_addr, sh_addr + sh_size)
        if sh_type != 2:  # SHT_SYMTAB
            continue
        str_offset = sections[sh_link][4]
        for j in range(sh_size // sh_entsize):
            st_name, st_value = struct.unpack_from(">II", data, sh_offset + j * sh_entsize)
            start = str_offset + st_name
            name = data[start : data.index(b"\0", start)].decode("ascii", "replace")
            if name in ("_SDA_BASE_", "_SDA2_BASE_"):
                symbols[name] = st_value

    if sdata is None or sdata2 is None:
        sys.exit(f"{path}: missing .sdata or .sdata2 section")
    # If the linker didn't emit the base symbols, use the EABI definition.
    symbols.setdefault("_SDA_BASE_", sdata + 0x8000)
    symbols.setdefault("_SDA2_BASE_", sdata2[0] + 0x8000)
    return symbols, sdata2


def fix_dol(path: str, sda_base: int, sda2_base: int, sdata2: Tuple[int, int]) -> int:
    with open(path, "rb") as f:
        dol = bytearray(f.read())
    offsets = struct.unpack_from(f">{DOL_SECTIONS}I", dol, 0x00)
    sizes = struct.unpack_from(f">{DOL_SECTIONS}I", dol, 0x90)

    fixed = 0
    for i in range(DOL_TEXT_SECTIONS):
        for pos in range(offsets[i], offsets[i] + sizes[i], 4):
            ins = struct.unpack_from(">I", dol, pos)[0]
            if ins >> 26 not in D_FORM_OPCODES or (ins >> 16) & 0x1F != 2:
                continue
            simm = ins & 0xFFFF
            if simm & 0x8000:
                simm -= 0x10000
            target = sda2_base + simm
            if not sdata2[0] <= target < sdata2[1]:
                continue
            new_simm = target - sda_base
            if not -0x8000 <= new_simm < 0x8000:
                sys.exit(f"{path}: {target:#010X} is out of r13 range at file offset {pos:#X}")
            ins = (ins & 0xFFE00000) | (13 << 16) | (new_simm & 0xFFFF)
            struct.pack_into(">I", dol, pos, ins)
            fixed += 1

    with open(path, "wb") as f:
        f.write(dol)
    return fixed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert an ELF to a DOL and apply ProDG small-data addressing."
    )
    parser.add_argument("dtk", help="path to decomp-toolkit")
    parser.add_argument("elf", help="linked ELF")
    parser.add_argument("dol", help="output DOL")
    args = parser.parse_args()

    result = subprocess.run([args.dtk, "elf2dol", args.elf, args.dol])
    if result.returncode != 0:
        sys.exit(result.returncode)

    symbols, sdata2 = read_elf_info(args.elf)
    fix_dol(args.dol, symbols["_SDA_BASE_"], symbols["_SDA2_BASE_"], sdata2)


if __name__ == "__main__":
    main()
