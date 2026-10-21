#ifndef GAME_VECTOR_H
#define GAME_VECTOR_H

// Three-float vector. The real name isn't known yet; the game's debug
// strings call matrices "MATRIX", so this follows that style.
//
// Copies are member by member (lfs/stfs), not a block move, so the class
// has its own copy constructor and assignment.
class VECTOR {
public:
    float x;
    float y;
    float z;

    VECTOR() {}
    VECTOR(const VECTOR& v) : x(v.x), y(v.y), z(v.z) {}
    VECTOR& operator=(const VECTOR& v) {
        x = v.x;
        y = v.y;
        z = v.z;
        return *this;
    }
};

#endif
