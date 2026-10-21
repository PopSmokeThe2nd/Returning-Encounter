#ifndef GAME_MODEL_H
#define GAME_MODEL_H

#include "types.h"
#include "game/vector.h"

// A placed model, from the code around the "models" string (0x800F33C8).
// The real class name isn't known yet, so "Model" is a placeholder, and so
// are the fn_<address> method names. Only the fields other files use are
// listed. It has no virtual functions: delete calls its destructor directly.
class Model {
public:
    ~Model();
    void fn_800F3828(float value);
    void fn_800F3B74(float value);

    /* 0x00 */ float m00;
    /* 0x04 */ VECTOR mPos;
    /* 0x10 */ u8 pad10[0x4];
    /* 0x14 */ float m14;
};

#endif
