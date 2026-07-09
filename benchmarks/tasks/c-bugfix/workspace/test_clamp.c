#include <assert.h>
#include "clamp.h"

int main(void) {
    assert(clamp_int(5, 0, 10) == 5);
    assert(clamp_int(-3, 0, 10) == 0);
    assert(clamp_int(12, 0, 10) == 10);
    return 0;
}
