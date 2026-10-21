#ifndef GAME_MODEL_H
#define GAME_MODEL_H

#include "types.h"
#include "game/vector.h"

class cAnimControl;

// A placed model, from the code around the "models" string (0x800F33C8).
// The real class name isn't known yet, so "Model" is a placeholder, and so
// are the fn_<address> method names. Only the fields other files use are
// named, but the size (0x40) is right because other files use new Model.
// It has no virtual functions: delete calls its destructor directly.
class Model {
public:
    // Takes over ANIM: the destructor calls anim->Release() and frees it.
    // If FLAG is set, the destructor first calls anim->m04->Slot02() too.
    Model(cAnimControl* anim, int flag);
    ~Model();
    void fn_800F3828(float value);
    void fn_800F3B74(float value);

    /* 0x00 */ float mScale; // uniform, fed to PSMTXScale
    /* 0x04 */ VECTOR mPos;
    /* 0x10 */ VECTOR mRot;  // radians, fed to PSMTXRotRad
    /* 0x1C */ u8 pad1C[0x8];
    /* 0x24 */ cAnimControl* mAnim;
    /* 0x28 */ u8 pad28[0x18];
};

#endif
