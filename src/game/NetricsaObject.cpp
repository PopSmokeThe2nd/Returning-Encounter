#include "game/NetricsaObject.h"
#include "game/Model.h"
#include "game/debug.h"
#include "game/memory.h"

CcNetricsaObject::CcNetricsaObject(int id, const VECTOR& pos) : mId(id), mModel(NULL), mPos(pos) {
    fn_80004254("CcNetricsaObject::CcNetricsaObject(%d)", mId);
}

CcNetricsaObject::~CcNetricsaObject() {
    fn_80004254("CcNetricsaObject::~CcNetricsaObject");
}

void CcNetricsaObject::fn_80103E7C() {
    if (mModel) {
        delete mModel;
        mModel = NULL;
    }
}

void CcNetricsaObject::fn_80103EC0(float value) {
    if (mModel) {
        mModel->m00 = m14;
        mModel->mPos = mPos;
        mModel->m14 = m18;
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

CcNetricsaItemObject::CcNetricsaItemObject(int id, const VECTOR& pos) : CcNetricsaObject(id, pos) {
    fn_80004254("CcNetricsaItemObject::CcNetricsaItemObject(%d)", mId);
}

CcNetricsaItemObject::~CcNetricsaItemObject() {
    fn_80004254("CcNetricsaItemObject::~CcNetricsaItemObject");
}
