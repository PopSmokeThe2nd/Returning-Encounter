MEMORY
{
    text : origin = $ORIGIN
}

SECTIONS
{
    GROUP:
    {
        $SECTIONS
        .stack ALIGN(0x100):{}
    } > text

    _stack_end = $LAST_SECTION_SYMBOL + SIZEOF($LAST_SECTION_NAME) + 0x20;
    _stack_addr = _stack_end + $STACKSIZE;
    _db_stack_addr = (_stack_addr + 0x2000);
    _db_stack_end = _stack_addr;
    __ArenaLo = _stack_addr + 0x20;
    __ArenaHi = $ARENAHI;
}

FORCEACTIVE
{
    $FORCEACTIVE
}
