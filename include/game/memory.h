#ifndef GAME_MEMORY_H
#define GAME_MEMORY_H

#include "types.h"

// The game replaces global new and delete with inline versions, so every
// new and delete expression expands to this code at the call site.
//
// Small blocks come from a pool (fn_80115E14 / fn_80115EDC). Anything the
// pool can't serve goes to a heap (fn_801160CC / fn_80116234), and the
// block header 0x18 bytes before the pointer holds the block's size.
// Names are placeholders until these are identified.

extern "C" void* fn_80115E14(u32 size);
extern "C" void fn_80115EDC(void* p);
extern "C" void* fn_801160CC(void* heap, u32 size);
extern "C" void fn_80116234(void* heap, void* p);

extern char* lbl_802DADB0;  // Pool end; pointers below it belong to the pool
extern s32 lbl_802DADA8;    // Free heap bytes
extern void* lbl_802DADB8;  // Heap

// The pool result is returned straight away, and the heap result has its
// own variable. With one variable for both results, the pool result is
// tested and kept in the same register ("mr. r31,r3"), which the game's
// code doesn't do.
inline void* operator new(unsigned int size) {
    void* p = fn_80115E14(size);
    if (p != NULL) {
        return p;
    }
    void* q = fn_801160CC(lbl_802DADB8, size);
    lbl_802DADA8 -= ((s32*)q)[-6];
    return q;
}

inline void operator delete(void* p) {
    if ((char*)p < lbl_802DADB0) {
        fn_80115EDC(p);
    } else {
        lbl_802DADA8 += ((s32*)p)[-6];
        fn_80116234(lbl_802DADB8, p);
    }
}

#endif
