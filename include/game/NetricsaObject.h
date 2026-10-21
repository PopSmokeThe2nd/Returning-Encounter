#ifndef GAME_NETRICSAOBJECT_H
#define GAME_NETRICSAOBJECT_H

#include "types.h"
#include "game/vector.h"

// An entry shown in NETRICSA, the in-game encyclopedia. Class names come from
// the game's debug strings. Methods named fn_<address> are placeholders.
class CcNetricsaObject {
public:
    CcNetricsaObject(int id, const VECTOR& pos);
    virtual ~CcNetricsaObject();
    virtual void Slot2(void* arg) = 0;
    virtual void fn_80103E7C();
    virtual void fn_80103EC0(float value);
    virtual void fn_80104834(float value) { m14 = value; }
    virtual void fn_8010483C(float value) { m18 = value; }
    virtual void fn_80104844(float value) { m1C = value; }

    /* 0x00 */ int mId;
    /* 0x04 */ void* mModel;
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
    virtual void Slot2(void* arg);
};

class CcNetricsaItemObject : public CcNetricsaObject {
public:
    CcNetricsaItemObject(int id, const VECTOR& pos);
    virtual ~CcNetricsaItemObject();
    virtual void Slot2(void* arg);
};

#endif
