#include <stddef.h>
#include <stdint.h>

int parse_packet(const uint8_t *buf, size_t len, uint16_t *out_value) {
    if (buf == 0 || out_value == 0 || len != 4) {
        return -1;
    }
    if (buf[0] != 0xAA) {
        return -1;
    }
    if (((uint8_t)(buf[1] + buf[2])) != buf[3]) {
        return -1;
    }
    *out_value = (uint16_t)(((uint16_t)buf[1] << 8) | buf[2]);
    return 0;
}
