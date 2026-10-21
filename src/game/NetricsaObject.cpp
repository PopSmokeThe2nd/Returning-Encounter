#include "game/NetricsaObject.h"
#include "game/AnimControl.h"
#include "game/Model.h"
#include "game/debug.h"
#include "game/memory.h"

extern "C" void* memset(void* dst, int value, unsigned int size);

// The model manager, and its lookup for model numbers up to 0xA4.
// Placeholder names.
extern void* lbl_802DA5B8;
extern "C" u32 fn_8010B938(void* manager, u32 id);

CcNetricsaObject::CcNetricsaObject(int id, const VECTOR& pos) : mId(id), mModel(NULL), mPos(pos) {
    fn_80004254("CcNetricsaObject::CcNetricsaObject(%d)", mId);
}

CcNetricsaObject::~CcNetricsaObject() {
    fn_80004254("CcNetricsaObject::~CcNetricsaObject");
}

void CcNetricsaObject::FreeModel() {
    if (mModel) {
        delete mModel;
        mModel = NULL;
    }
}

void CcNetricsaObject::UpdateModel(float value) {
    if (mModel) {
        mModel->mScale = m14;
        mModel->mPos = mPos;
        mModel->mRot.y = m18;
        mModel->fn_800F3B74(m1C);
        mModel->fn_800F3828(value);
    }
}

CcNetricsaEnemyObject::CcNetricsaEnemyObject(int id, const VECTOR& pos) : CcNetricsaObject(id, pos) {
    fn_80004254("CcNetricsaEnemyObject::CcNetricsaEnemyObject(%d)", mId);
}

CcNetricsaEnemyObject::~CcNetricsaEnemyObject() {
    fn_80004254("CcNetricsaEnemyObject::~CcNetricsaEnemyObject");
}

void CcNetricsaEnemyObject::CreateModel(void* arg) {
    if (mModel == NULL) {
        cMinionAnimControl* anim = new cMinionAnimControl;
        anim->mMinionType = mId;
        anim->Init();
        anim->fn_80003594(mId, arg);
        if (anim->HasClip(e_AnimWalk)) {
            anim->PlayClip(e_AnimWalk, 1, 1.0f);
            fn_80004254("e_AnimWalk");
        } else if (anim->HasClip(e_AnimRun)) {
            anim->PlayClip(e_AnimRun, 1, 1.0f);
            fn_80004254("e_AnimRun");
        } else if (anim->HasClip(e_AnimSwim)) {
            anim->PlayClip(e_AnimSwim, 1, 1.0f);
            fn_80004254("e_AnimSwim");
        } else if (anim->HasClip(e_AnimIdle)) {
            anim->PlayClip(e_AnimIdle, 1, 1.0f);
            fn_80004254("e_AnimIdle");
        } else if (anim->HasClip(e_AnimHover)) {
            anim->PlayClip(e_AnimHover, 1, 1.0f);
            fn_80004254("e_AnimHover");
        }
        mModel = new Model(anim, 0);
    }
}

CcNetricsaItemObject::CcNetricsaItemObject(int id, const VECTOR& pos) : CcNetricsaObject(id, pos) {
    fn_80004254("CcNetricsaItemObject::CcNetricsaItemObject(%d)", mId);
}

CcNetricsaItemObject::~CcNetricsaItemObject() {
    fn_80004254("CcNetricsaItemObject::~CcNetricsaItemObject");
}

void CcNetricsaItemObject::CreateModel(void* arg) {
    if (mModel == NULL) {
        cAnimControl* anim = new cAnimControl;
        anim->SetClips(NULL);
        anim->fn_80003594(mId, arg);
        mModel = new Model(anim, 0);
    }
}

CcNetricsaEnemyPartsObject::CcNetricsaEnemyPartsObject(int id, const VECTOR& pos, const NetricsaPart* parts)
    : CcNetricsaEnemyObject(id, pos), mPartList(parts) {
    memset(mParts, 0, sizeof(mParts));
}

CcNetricsaEnemyPartsObject::~CcNetricsaEnemyPartsObject() {
}

void CcNetricsaEnemyPartsObject::CreateModel(void* arg) {
    CcNetricsaEnemyObject::CreateModel(arg);
    cAnimObject* skeleton = mModel->mAnim->m04;
    const NetricsaPart* part = mPartList;
    for (int i = 0; part->mModelId != 0; part++, i++) {
        cAnimControl* anim = new cAnimControl;
        int bone = -1;
        anim->SetClips(NULL);
        u32 modelId = part->mModelId;
        if (modelId <= 0xA4) {
            modelId = fn_8010B938(lbl_802DA5B8, modelId);
        }
        anim->fn_800034A0(modelId, arg);
        mParts[i] = new Model(anim, 0);
        anim->m04->Slot02();
        if (part->mBone != NULL) {
            bone = skeleton->FindBone(part->mBone);
        }
        mBones[i] = bone;
    }
}

void CcNetricsaEnemyPartsObject::FreeModel() {
    const NetricsaPart* part = mPartList;
    for (int i = 0; part->mModelId != 0; part++, i++) {
        delete mParts[i];
    }
    memset(mParts, 0, sizeof(mParts));
    CcNetricsaEnemyObject::FreeModel();
}

void CcNetricsaEnemyPartsObject::UpdateModel(float value) {
    CcNetricsaEnemyObject::UpdateModel(value);
    const NetricsaPart* part = mPartList;
    for (int i = 0; part->mModelId != 0; part++, i++) {
        if (mBones[i] != -1) {
            VECTOR pos;
            mModel->mAnim->GetBonePos(mBones[i], &pos);
            mParts[i]->mPos = pos;
        }
        mParts[i]->mScale = m14;
        mParts[i]->mRot = mModel->mRot;
        mParts[i]->fn_800F3B74(m1C);
        mParts[i]->fn_800F3828(value);
    }
}
