#include "game/NetricsaObject.h"
#include "game/debug.h"
#include "game/memory.h"

CcNetricsaObject::CcNetricsaObject(int id, const VECTOR& pos) : mId(id), mModel(NULL), mPos(pos) {
    fn_80004254("CcNetricsaObject::CcNetricsaObject(%d)", mId);
}

CcNetricsaObject::~CcNetricsaObject() {
    fn_80004254("CcNetricsaObject::~CcNetricsaObject");
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
