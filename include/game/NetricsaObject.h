#ifndef GAME_NETRICSAOBJECT_H
#define GAME_NETRICSAOBJECT_H

#include "types.h"
#include "game/vector.h"

class Model;

// An entry shown in NETRICSA, the in-game encyclopedia. Class names come from
// the game's debug strings. Methods named fn_<address> are placeholders, and
// so are CreateModel, FreeModel and UpdateModel.
class CcNetricsaObject {
public:
    CcNetricsaObject(int id, const VECTOR& pos);
    virtual ~CcNetricsaObject();
    // Creates mModel if there isn't one yet. ARG goes to the animation
    // controller's load methods; its type isn't known yet.
    virtual void CreateModel(void* arg) = 0;
    virtual void FreeModel();
    virtual void UpdateModel(float value);
    virtual void fn_80104834(float value) { m14 = value; }
    virtual void fn_8010483C(float value) { m18 = value; }
    virtual void fn_80104844(float value) { m1C = value; }

    /* 0x00 */ int mId;
    /* 0x04 */ Model* mModel;
    /* 0x08 */ VECTOR mPos;
    /* 0x14 */ float m14;
    /* 0x18 */ float m18;
    /* 0x1C */ float m1C;
    // 0x20: vtable pointer (g++ 2.95 puts it after the fields)
};

class CcNetricsaEnemyObject : public CcNetricsaObject {
public:
    CcNetricsaEnemyObject(int id, const VECTOR& pos);
    virtual ~CcNetricsaEnemyObject();
    virtual void CreateModel(void* arg);
};

class CcNetricsaItemObject : public CcNetricsaObject {
public:
    CcNetricsaItemObject(int id, const VECTOR& pos);
    virtual ~CcNetricsaItemObject();
    virtual void CreateModel(void* arg);
};

// An extra model attached to a bone of the main model. A list of these ends
// with an entry whose mModelId is 0. The struct name is a placeholder.
struct NetricsaPart {
    /* 0x00 */ u32 mModelId;      // 0xA4 or less: looked up through fn_8010B938
    /* 0x04 */ const char* mBone; // NULL: not attached to a bone
};

// An enemy with extra part models. The class name is a placeholder: unlike
// the classes above it prints no debug strings. It must stay declared after
// CcNetricsaItemObject, because g++ emits the vtables in reverse order of
// declaration and this one comes first in .rodata.
class CcNetricsaEnemyPartsObject : public CcNetricsaEnemyObject {
public:
    CcNetricsaEnemyPartsObject(int id, const VECTOR& pos, const NetricsaPart* parts);
    virtual ~CcNetricsaEnemyPartsObject();
    virtual void CreateModel(void* arg);
    virtual void FreeModel();
    virtual void UpdateModel(float value);

    /* 0x024 */ const NetricsaPart* mPartList;
    /* 0x028 */ Model* mParts[32];
    /* 0x0A8 */ int mBones[32]; // -1: the part doesn't follow a bone
};

#endif
