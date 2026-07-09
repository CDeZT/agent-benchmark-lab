#include <assert.h>
#include <stdint.h>
#include "packet.h"

int main(void) {
    uint16_t value = 0;
    const uint8_t good[] = {0xAA, 0x12, 0x34, 0x46};
    const uint8_t bad_header[] = {0x00, 0x12, 0x34, 0x46};
    const uint8_t bad_checksum[] = {0xAA, 0x12, 0x34, 0x45};

    assert(parse_packet(good, sizeof(good), &value) == 0);
    assert(value == 0x1234);
    assert(parse_packet(bad_header, sizeof(bad_header), &value) == -1);
    assert(parse_packet(bad_checksum, sizeof(bad_checksum), &value) == -1);
    assert(parse_packet(good, 2, &value) == -1);
    assert(parse_packet(good, sizeof(good), 0) == -1);
    return 0;
}
