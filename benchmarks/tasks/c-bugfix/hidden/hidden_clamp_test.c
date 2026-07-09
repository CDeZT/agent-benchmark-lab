#include <assert.h>
#include "clamp.h"

int main(void) {
    assert(clamp_int(0, 0, 10) == 0);
    assert(clamp_int(10, 0, 10) == 10);
    assert(clamp_int(-100, -5, 5) == -5);
    assert(clamp_int(100, -5, 5) == 5);
    return 0;
}
