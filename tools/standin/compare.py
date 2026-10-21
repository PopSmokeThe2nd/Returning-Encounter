#!/usr/bin/env python3

###
# Compares the functions in a compiled object with decomp-toolkit's assembly
# for the same unit, one function at a time.
#
# Usage:
#   python tools/standin/compare.py build/standin/obj/src/game/NetricsaObject.o \
#       build/G3BE9G/asm/game/NetricsaObject.s [-v]
#
# The .s comes from decomp-toolkit, so run python configure.py && ninja
# first (it needs the game's DOL: your disc image in orig/G3BE9G).
#
# Functions are paired by name (use --map for renames). Each instruction is
# compared as a 32-bit word with the relocated bits masked out, plus the
# relocation itself: same kind (@ha, @l, @sda21, branch) and same target.
# A target inside the unit's own data (strings, floats, vtables that
# symbols.txt hasn't named yet) is compared as section + offset, so the
# object's data layout has to match too. Data contents are not compared;
# objdiff remains the final word.
#
# Exit status: 0 when every function matches, 1 otherwise.
###

import argparse
import difflib
import os
import re
import shutil
import signal
import struct
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent.parent
EXE = ".exe" if os.name == "nt" else ""

# PowerPC ELF relocation types -> (kind, mask of the bits they fill in)
R_PPC = {
    1: ("addr32", 0xFFFFFFFF),  # R_PPC_ADDR32
    2: ("addr24", 0x03FFFFFC),  # R_PPC_ADDR24
    3: ("addr16", 0x0000FFFF),  # R_PPC_ADDR16
    4: ("l", 0x0000FFFF),  # R_PPC_ADDR16_LO
    5: ("h", 0x0000FFFF),  # R_PPC_ADDR16_HI
    6: ("ha", 0x0000FFFF),  # R_PPC_ADDR16_HA
    7: ("addr14", 0x0000FFFC),  # R_PPC_ADDR14
    10: ("rel24", 0x03FFFFFC),  # R_PPC_REL24
    11: ("rel14", 0x0000FFFC),  # R_PPC_REL14
    12: ("rel14", 0x0000FFFC),  # R_PPC_REL14_BRTAKEN
    13: ("rel14", 0x0000FFFC),  # R_PPC_REL14_BRNTAKEN
    32: ("sda21", 0x001FFFFF),  # R_PPC_SDAREL16 (base register included)
    109: ("sda21", 0x001FFFFF),  # R_PPC_EMB_SDA21
}
# dtk operand suffixes -> (kind, mask)
DTK_RELOC = {
    "ha": ("ha", 0x0000FFFF),
    "h": ("h", 0x0000FFFF),
    "l": ("l", 0x0000FFFF),
    "sda21": ("sda21", 0x001FFFFF),
    "sda2": ("sda21", 0x001FFFFF),
}

SymKey = Tuple  # ("sym", name, addend) or ("sec", section, offset)


class Insn(NamedTuple):
    offset: int  # from the start of the function
    word: int  # masked
    reloc: Optional[Tuple[str, SymKey]]
    text: str

    def key(self) -> Tuple:
        return (self.word, self.reloc)


class CompareError(Exception):
    pass


###
# Our object (ELF)
###


class ElfSymbol(NamedTuple):
    name: str
    value: int
    size: int
    type: int
    bind: int
    shndx: int


class ElfObject:
    def __init__(self, path: Path):
        try:
            data = path.read_bytes()
        except OSError as e:
            raise CompareError(f"cannot read {path}: {e.strerror or e}")
        if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 2:
            raise CompareError(f"{path} is not a 32-bit big-endian ELF object")
        (_, _, _, _, _, _, shoff, _, _, _, _, shentsize, shnum, shstrndx) = struct.unpack_from(
            ">16sHHIIIIIHHHHHH", data, 0
        )
        self.sections = []
        for i in range(shnum):
            self.sections.append(struct.unpack_from(">IIIIIIIIII", data, shoff + i * shentsize))
        strtab_off = self.sections[shstrndx][4]
        self.section_names = [self._str(data, strtab_off, s[0]) for s in self.sections]
        self.data = data
        self.symbols: List[ElfSymbol] = []
        self.relocs: Dict[int, Dict[int, Tuple[int, int, int]]] = {}  # shndx -> offset -> (type, sym, addend)
        for idx, sec in enumerate(self.sections):
            sh_type, sh_offset, sh_size, sh_link, sh_info = sec[1], sec[4], sec[5], sec[6], sec[7]
            if sh_type == 2:  # SHT_SYMTAB
                str_off = self.sections[sh_link][4]
                for off in range(sh_offset, sh_offset + sh_size, 16):
                    st_name, st_value, st_size, st_info, _, st_shndx = struct.unpack_from(">IIIBBH", data, off)
                    self.symbols.append(
                        ElfSymbol(self._str(data, str_off, st_name), st_value, st_size, st_info & 0xF, st_info >> 4, st_shndx)
                    )
        for idx, sec in enumerate(self.sections):
            sh_type, sh_offset, sh_size, sh_info = sec[1], sec[4], sec[5], sec[7]
            if sh_type in (4, 9):  # SHT_RELA, SHT_REL
                entsize = 12 if sh_type == 4 else 8
                table = self.relocs.setdefault(sh_info, {})
                for off in range(sh_offset, sh_offset + sh_size, entsize):
                    if sh_type == 4:
                        r_offset, r_info, r_addend = struct.unpack_from(">IIi", data, off)
                    else:
                        r_offset, r_info = struct.unpack_from(">II", data, off)
                        r_addend = 0
                    table[r_offset] = (r_info & 0xFF, r_info >> 8, r_addend)

    @staticmethod
    def _str(data: bytes, base: int, off: int) -> str:
        end = data.index(b"\0", base + off)
        return data[base + off : end].decode("latin-1")

    def is_exec(self, shndx: int) -> bool:
        return 0 < shndx < len(self.sections) and bool(self.sections[shndx][2] & 0x4)

    def section_bytes(self, shndx: int) -> bytes:
        sec = self.sections[shndx]
        if sec[1] == 8:  # SHT_NOBITS
            return b""
        return self.data[sec[4] : sec[4] + sec[5]]

    def functions(self) -> List[Tuple[str, int, int, int]]:
        """(name, section, start, size) for every function, in address order."""
        funcs = []
        by_section: Dict[int, List[ElfSymbol]] = {}
        for sym in self.symbols:
            if self.is_exec(sym.shndx) and sym.type == 2:  # STT_FUNC
                by_section.setdefault(sym.shndx, []).append(sym)
        for shndx, syms in sorted(by_section.items()):
            syms.sort(key=lambda s: s.value)
            sec_size = self.sections[shndx][5]
            for i, sym in enumerate(syms):
                size = sym.size
                if size == 0:
                    size = (syms[i + 1].value if i + 1 < len(syms) else sec_size) - sym.value
                funcs.append((sym.name, shndx, sym.value, size))
        return funcs


###
# decomp-toolkit assembly
###

INSN_RE = re.compile(r"^/\*\s*([0-9A-Fa-f]{8})\s+[0-9A-Fa-f]{8}\s+((?:[0-9A-Fa-f]{2}\s*){4})\*/\s*(.*)$")
LOC_RE = re.compile(r"^#\s*(\.[\w.]+):(0x[0-9A-Fa-f]+)\s*\|\s*(0x[0-9A-Fa-f]+)")
NAME = r'(?:"[^"]+"|[A-Za-z_.$?@][\w.$?@<>:-]*?)'
SYMREF_RE = re.compile(r"(" + NAME + r")(?:([+-])(0x[0-9A-Fa-f]+|\d+))?@(ha|h|l|sda21|sda2)\b")


def unquote(name: str) -> str:
    return name[1:-1] if name.startswith('"') else name


class TargetAsm:
    def __init__(self, path: Path):
        self.functions: Dict[str, List[Tuple[int, int, str]]] = {}  # name -> [(addr, word, text)]
        self.order: List[str] = []
        self.objects: Dict[str, Tuple[str, int]] = {}  # data symbol -> (section, offset)
        self.names = set()
        loc: Optional[Tuple[str, int]] = None
        current = None
        try:
            text = path.read_text(errors="replace")
        except FileNotFoundError:
            raise CompareError(
                f"{path} not found. dtk writes the unit's assembly during the normal build: "
                "run python configure.py && ninja first (it needs the game's DOL: put your disc image in orig/G3BE9G)."
            )
        except OSError as e:
            raise CompareError(f"cannot read {path}: {e.strerror or e}")
        for line in text.splitlines():
            stripped = line.strip()
            m = LOC_RE.match(stripped)
            if m:
                loc = (m.group(1), int(m.group(2), 16))
                continue
            m = re.match(r"\.fn\s+(" + NAME + r")\s*,", stripped)
            if m:
                current = unquote(m.group(1))
                loc = None
                self.functions[current] = []
                self.order.append(current)
                self.names.add(current)
                continue
            if stripped.startswith(".endfn"):
                current = None
                continue
            m = re.match(r"\.(obj|sym)\s+(" + NAME + r")\s*,", stripped)
            if m:
                name = unquote(m.group(2))
                self.names.add(name)
                if m.group(1) == "obj" and loc and not loc[0].startswith((".text", ".init")):
                    self.objects[name] = loc
                loc = None
                continue
            if current is None:
                continue
            m = INSN_RE.match(stripped)
            if m:
                word = int(m.group(2).replace(" ", ""), 16)
                text = re.sub(r"\s+", " ", m.group(3).strip())
                self.functions[current].append((int(m.group(1), 16), word, text))
                for ref in SYMREF_RE.finditer(text):
                    self.names.add(unquote(ref.group(1)))
        if not self.functions:
            raise CompareError(f"no functions (.fn) found in {path}")


###
# Normalization
###


def sign_extend(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


class Comparer:
    def __init__(self, obj: ElfObject, target: TargetAsm, symmap: Dict[str, str]):
        self.obj = obj
        self.target = target
        self.symmap = symmap
        self.our_names = {s.name for s in obj.symbols if s.name}
        self.our_defined = {
            s.name: s for s in obj.symbols if s.name and s.shndx not in (0, 0xFFF1, 0xFFF2) and s.type in (0, 1, 2)
        }
        self.target_names = {symmap.get(n, n) for n in target.names}

    # --- our side
    def our_symkey(self, symidx: int, addend: int) -> SymKey:
        sym = self.obj.symbols[symidx]
        if sym.type == 3 or not sym.name:  # STT_SECTION
            return ("sec", self.obj.section_names[sym.shndx], addend)
        if sym.name in self.target_names:
            return ("sym", sym.name, addend)
        if sym.name in self.our_defined and not self.obj.is_exec(sym.shndx) and sym.shndx < len(self.obj.sections):
            return ("sec", self.obj.section_names[sym.shndx], sym.value + addend)
        return ("sym", sym.name, addend)

    def our_function(self, shndx: int, start: int, size: int, texts: Dict[Tuple[int, int], str]) -> List[Insn]:
        code = self.obj.section_bytes(shndx)
        relocs = self.obj.relocs.get(shndx, {})
        funcs_at = {
            s.value: s.name for s in self.obj.symbols if s.shndx == shndx and s.type == 2 and s.name
        }
        insns = []
        for off in range(start, start + size, 4):
            word = struct.unpack_from(">I", code, off)[0]
            reloc = None
            for roff in (off, off + 2, off + 1, off + 3):
                if roff in relocs:
                    rtype, symidx, addend = relocs[roff]
                    kind, mask = R_PPC.get(rtype, (f"R{rtype}", 0xFFFFFFFF))
                    word &= ~mask
                    reloc = (kind, self.our_symkey(symidx, addend))
                    break
            if reloc is None and word >> 26 == 18:
                # A branch the assembler resolved itself: to another function
                # in this section, compare it by name like dtk shows it.
                disp = sign_extend(word & 0x03FFFFFC, 26)
                dest = disp if word & 2 else off + disp
                if not (start <= dest < start + size) and dest in funcs_at:
                    word &= ~0x03FFFFFC
                    name = funcs_at[dest]
                    reloc = ("rel24", ("sym", name, 0))
            if (shndx, off) in texts:
                text = pretty_objdump(texts[(shndx, off)], reloc, start)
            else:
                raw = struct.unpack_from(">I", code, off)[0]
                text = f".4byte {raw:#010x}" + describe_reloc(reloc)
            insns.append(Insn(off - start, word, reloc, text))
        return insns

    # --- target side
    def target_symkey(self, raw: str, sign: Optional[str], add: Optional[str]) -> SymKey:
        name = unquote(raw)
        addend = int(add, 0) if add else 0
        if sign == "-":
            addend = -addend
        mapped = self.symmap.get(name, name)
        if mapped in self.our_names:
            return ("sym", mapped, addend)
        if name in self.target.objects:
            section, offset = self.target.objects[name]
            return ("sec", section, offset + addend)
        return ("sym", mapped, addend)

    def target_function(self, name: str) -> List[Insn]:
        lines = self.target.functions[name]
        start = lines[0][0] if lines else 0
        insns = []
        for addr, word, text in lines:
            reloc = None
            text = re.sub(r"\.L_([0-9A-Fa-f]{8})\b", lambda m: f".L+{int(m.group(1), 16) - start:#x}", text)
            m = SYMREF_RE.search(text)
            if m:
                kind, mask = DTK_RELOC[m.group(4)]
                word &= ~mask
                reloc = (kind, self.target_symkey(m.group(1), m.group(2), m.group(3)))
            else:
                op = word >> 26
                parts = text.split(None, 1)
                mnemonic = parts[0] if parts else ""
                operand = parts[1].split(",")[-1].strip() if len(parts) > 1 else ""
                if op in (16, 18) and mnemonic.startswith("b") and operand and not operand.startswith(".L"):
                    if re.fullmatch(NAME, operand) and not re.fullmatch(r"(?:cr\d|0x[0-9A-Fa-f]+|-?\d+)", operand):
                        if op == 18:
                            word &= ~0x03FFFFFC
                            reloc = ("rel24", self.target_symkey(operand, None, None))
                        else:
                            word &= ~0x0000FFFC
                            reloc = ("rel14", self.target_symkey(operand, None, None))
            insns.append(Insn(addr - start, word, reloc, text))
        return insns


def symkey_text(key: SymKey) -> str:
    what, name, offset = key
    if offset == 0 and what == "sym":
        return name
    return f"{name}{'-' if offset < 0 else '+'}{abs(offset):#x}"


def describe_reloc(reloc: Optional[Tuple[str, SymKey]]) -> str:
    if reloc is None:
        return ""
    return f"  [{reloc[0]} {symkey_text(reloc[1])}]"


def pretty_objdump(text: str, reloc: Optional[Tuple[str, SymKey]], func_start: int) -> str:
    """Make objdump's syntax look like dtk's, so equal lines read the same."""
    mnemonic, _, ops = text.partition(" ")
    ops = ops.replace(",", ", ")
    ops = re.sub(r"4\*(cr\d)\+(lt|gt|eq|so)", r"\1\2", ops)
    ops = re.sub(r"^(lt|gt|eq|so)$", r"cr0\1", ops)
    branch = re.match(r"^((?:cr\d, )?)([0-9a-f]+) <[^>]*>$", ops)
    if branch:
        if reloc and reloc[0] in ("rel24", "rel14"):
            ops = branch.group(1) + symkey_text(reloc[1])
        else:
            ops = branch.group(1) + f".L+{int(branch.group(2), 16) - func_start:#x}"
    else:
        ops = re.sub(r"(?<![\w.+])(-?)(\d+)\b", lambda m: f"{m.group(1)}{int(m.group(2)):#x}", ops)
        if reloc and reloc[0] == "sda21":
            # dtk shows small-data accesses as sym@sda21(r0) whatever the base.
            ops = re.sub(r"\b0x0\((?:r\d+|0x0)\)$", f"{symkey_text(reloc[1])}@sda21(r0)", ops)
        elif reloc and reloc[0] in ("ha", "h", "l"):
            sym = f"{symkey_text(reloc[1])}@{reloc[0]}"
            if re.search(r"\b0x0\(r\d+\)$", ops):
                ops = re.sub(r"\b0x0(\(r\d+\))$", sym + r"\1", ops)
            elif ops.endswith(", 0x0"):
                ops = ops[: -len("0x0")] + sym
    return f"{mnemonic} {ops}" if ops else mnemonic


def objdump_texts(objdump: Optional[str], obj_path: Path) -> Dict[Tuple[int, int], str]:
    """(section index, offset) -> disassembly text for our object."""
    if not objdump:
        return {}
    try:
        out = subprocess.run(
            [objdump, "-d", "-z", "--no-show-raw-insn", str(obj_path)], capture_output=True, text=True
        ).stdout
    except OSError:
        return {}
    texts = {}
    section = None
    names = ElfObject(obj_path).section_names
    for line in out.splitlines():
        m = re.match(r"Disassembly of section (\S+):", line)
        if m:
            section = names.index(m.group(1)) if m.group(1) in names else None
            continue
        m = re.match(r"\s+([0-9a-f]+):\s+(.*)$", line)
        if m and section is not None:
            text = re.sub(r"\s+", " ", m.group(2).split("#")[0].strip())
            texts[(section, int(m.group(1), 16))] = text
    return texts


def find_objdump(args) -> Optional[str]:
    if args.objdump:
        return args.objdump
    candidate = args.binutils / f"powerpc-eabi-objdump{EXE}"
    if candidate.is_file():
        return str(candidate)
    return shutil.which("powerpc-eabi-objdump")


def print_diff(t: List[Insn], o: List[Insn], context: int) -> None:
    sm = difflib.SequenceMatcher(None, [i.key() for i in t], [i.key() for i in o], autojunk=False)
    for group in sm.get_grouped_opcodes(context):
        print("    @@")
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for ins in t[i1:i2]:
                    print(f"      {ins.offset:#06x}  {ins.text}")
                continue
            for ins in t[i1:i2]:
                print(f"    - {ins.offset:#06x}  {ins.text}{describe_reloc(ins.reloc)}")
            for ins in o[j1:j2]:
                print(f"    + {ins.offset:#06x}  {ins.text}{describe_reloc(ins.reloc)}")


def read_symmap(path: Optional[Path]) -> Dict[str, str]:
    symmap = {}
    if path:
        for line in path.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                a, b = (x.strip() for x in line.split("=", 1))
                symmap[a] = b
    return symmap


def main() -> None:
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)  # quiet when piped into head
    parser = argparse.ArgumentParser(description="Compare an object's functions with dtk's target assembly.")
    parser.add_argument("object", type=Path, help="compiled object (.o)")
    parser.add_argument("target", type=Path, help="dtk assembly for the unit, e.g. build/G3BE9G/asm/game/NetricsaObject.s")
    parser.add_argument("-v", "--verbose", action="store_true", help="show the differing instructions")
    parser.add_argument("-f", "--function", action="append", default=[], help="only compare this function (repeatable)")
    parser.add_argument("--map", type=Path, help="file of 'target_name = our_name' lines for functions/symbols named differently")
    parser.add_argument("--context", type=int, default=3, help="lines of context in -v diffs (default: 3)")
    parser.add_argument("--binutils", type=Path, default=ROOT / "build" / "binutils", help="binutils directory, for objdump (default: build/binutils)")
    parser.add_argument("--objdump", help="objdump to disassemble our object for -v (default: powerpc-eabi-objdump from --binutils)")
    args = parser.parse_args()

    try:
        obj = ElfObject(args.object)
        target = TargetAsm(args.target)
        symmap = read_symmap(args.map)
        cmp = Comparer(obj, target, symmap)
        texts = objdump_texts(find_objdump(args), args.object) if args.verbose else {}
        ours = {name: (shndx, start, size) for name, shndx, start, size in obj.functions()}

        names = target.order
        if args.function:
            names = [n for n in names if n in args.function]
            unknown = set(args.function) - set(target.order)
            if unknown:
                raise CompareError(f"not in {args.target}: {', '.join(sorted(unknown))}")
        matched = 0
        problems = 0
        extra = 0
        paired = set()
        for tname in names:
            oname = symmap.get(tname, tname)
            if oname not in ours:
                print(f"MISSING {tname}" + (f" (looked for {oname})" if oname != tname else ""))
                problems += 1
                continue
            paired.add(oname)
            t = cmp.target_function(tname)
            o = cmp.our_function(*ours[oname], texts)
            if [i.key() for i in t] == [i.key() for i in o]:
                print(f"MATCH   {tname}")
                matched += 1
                continue
            problems += 1
            sm = difflib.SequenceMatcher(None, [i.key() for i in t], [i.key() for i in o], autojunk=False)
            ndiff = sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")
            print(f"DIFF    {tname}  (ours {len(o)} insns, target {len(t)}, {ndiff} differ)")
            if args.verbose:
                print_diff(t, o, args.context)
        if not args.function:
            for name in ours:
                if name not in paired:
                    print(f"EXTRA   {name} (not in the target unit)")
                    problems += 1
                    extra += 1
        summary = f"{matched}/{len(names)} functions match"
        if extra:
            summary += f", {extra} extra function(s) in the object"
        print(summary)
    except CompareError as e:
        sys.exit(f"compare.py: error: {e}")
    sys.exit(0 if problems == 0 else 1)


if __name__ == "__main__":
    main()
