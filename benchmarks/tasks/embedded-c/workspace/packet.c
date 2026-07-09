#include <stddef.h>
#include <stdint.h>

int parse_packet(const uint8_t *buf, size_t len, uint16_t *out_value) {
    if (len < 3) {
        return -1;
    }
    *out_value = (uint16_t)(buf[1] + buf[2]);
    return 0;
}
