#ifndef GAME_ANIMCONTROL_H
#define GAME_ANIMCONTROL_H

#include "types.h"
#include "game/vector.h"

// Animation controllers, from the code at 0x800034A0 (cAnimControlBase and
// cAnimControl) and 0x80004AA0 (cMinionAnimControl). The names cAnimControl
// and cMinionAnimControl come from the debug strings "cAnimControl::PlayClip()
// - (spaz noise), i haven't got a %d" and "%08x cMinionAnimControl::
// ClearCustomAnim()". cAnimControlBase, cAnimObject, cAnimClip and every
// method name except PlayClip are placeholders. A fn_<address> name is the
// address of the first class's version of that virtual function; the
// comments give the addresses of the overrides. Parameter lists of methods
// this code doesn't call have not been checked.
//
// None of the virtual functions are defined inline, so the vtables are
// emitted with the code that defines those functions, not by every user.
// Every override is declared: g++ 2.95 lets a class that overrides nothing
// share its base's vtable, and these classes each have their own.
//
// The controllers have no destructor. Model's destructor calls Release()
// and then frees the controller with the global delete.

// What a controller drives (m04): a model resource from the model manager.
// Its vtable pointer is at 0x0. Only slot 2 and slot 11 are known to be used.
class cAnimObject {
public:
    virtual void Slot01();
    virtual void Slot02(); // also called by Model's destructor when its flag is set
    virtual void Slot03();
    virtual void Slot04();
    virtual void Slot05();
    virtual void Slot06();
    virtual void Slot07();
    virtual void Slot08();
    virtual void Slot09();
    virtual void Slot10();
    virtual int FindBone(const char* name); // -1: not found (guess)
};

// Clip numbers, the index into a clip table. The names come from the debug
// strings in NetricsaObject.cpp, and the values from the clip name table at
// 0x801E18D4 ("idle1", "walk1;walk2", "run1;run2;run3", then "recoilforward1",
// "recoilback1", "blockrecoilforward" and "blockrecoilback" for 3-6, then
// "swim1;swim2" and "hover1;hover2"). It has 0x27 entries in all.
enum {
    e_AnimIdle = 0,
    e_AnimWalk = 1,
    e_AnimRun = 2,
    e_AnimSwim = 7,
    e_AnimHover = 8
};

// One entry of a controller's clip table.
struct cAnimClip {
    /* 0x00 */ int mAnim; // -1: this clip isn't available
    /* 0x04 */ float mSpeed;
    /* 0x08 */ int m08;
};

// Vtable at 0x801E1138.
class cAnimControlBase {
public:
    virtual void Init();    // fn_800035FC
    virtual void Release(); // fn_80003614
    virtual cAnimObject* fn_800034A0(u32 modelId, void* arg);
    virtual cAnimObject* fn_80003594(u32 modelId, void* arg);
    virtual void fn_8000366C();
    virtual void fn_800042A0();
    virtual void fn_80003734();

    /* 0x00 */ void* m00;
    /* 0x04 */ cAnimObject* m04;
    /* 0x08 */ u16 m08;
    /* 0x0A */ u16 m0A;
    // 0x0C: vtable pointer (g++ 2.95 puts it after the fields)
};

// Size 0x2C, vtable at 0x801E1090.
class cAnimControl : public cAnimControlBase {
public:
    virtual void Init();        // fn_800042EC
    virtual void Release();     // fn_800039E8
    virtual void fn_8000366C(); // fn_80003A1C

    virtual void SetClips(const cAnimClip* clips);         // fn_80003898
    virtual void PlayClip(int clip, int arg, float speed); // fn_80003B1C
    virtual void fn_80003C78();
    virtual void fn_8000430C();
    virtual void fn_80004330();
    virtual void fn_80004384();
    virtual void fn_800044BC();
    virtual void fn_800045F4();
    virtual int GetBonePos(int bone, VECTOR* pos); // fn_800046C4
    virtual void fn_80004794();
    virtual void fn_800041B8();
    virtual void fn_80004214();

    // Whether the model has CLIP. Without a clip table, every clip counts.
    // The wrappers at 0x80096A80 and 0x800B7514 inline the same test.
    bool HasClip(int clip) const {
        if (mClips != NULL) {
            return mClips[clip].mAnim != -1;
        }
        return true;
    }

    /* 0x10 */ int m10;
    /* 0x14 */ int m14;
    /* 0x18 */ const cAnimClip* mClips; // NULL: every clip is available
    /* 0x1C */ float m1C;
    /* 0x20 */ int m20;
    /* 0x24 */ int m24;
    /* 0x28 */ void* m28;
};

// Size 0x40, vtable at 0x801E15B0. Init picks the clip table for mMinionType.
class cMinionAnimControl : public cAnimControl {
public:
    virtual void Init();    // fn_80004AA0
    virtual void Release(); // fn_80004AFC
    virtual cAnimObject* fn_80003594(u32 modelId, void* arg); // fn_80004B1C
    virtual void PlayClip(int clip, int arg, float speed);    // fn_80004D00
    virtual void fn_8000430C(); // fn_80004D94
    virtual void fn_80004330(); // fn_80004D5C
    virtual void fn_80004794(); // fn_80004B98
    virtual void fn_800041B8(); // fn_80004C10

    /* 0x2C */ int mMinionType;
    /* 0x30 */ u32 mFlags;
    /* 0x34 */ int mCustomAnim;
    /* 0x38 */ float m38;
    /* 0x3C */ int m3C;
};

#endif
