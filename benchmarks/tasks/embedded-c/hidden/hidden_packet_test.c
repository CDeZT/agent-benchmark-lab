#include <assert.h>
#include <stdint.h>
#include "packet.h"

int main(void) {
    uint16_t value = 0;
    const uint8_t zero_payload[] = {0xAA, 0x00, 0x00, 0x00};
    const uint8_t wrapped_checksum[] = {0xAA, 0xFF, 0x02, 0x01};
    const uint8_t too_long[] = {0xAA, 0x01, 0x02, 0x03, 0x00};

    assert(parse_packet(zero_payload, sizeof(zero_payload), &value) == 0);
    assert(value == 0x0000);
    assert(parse_packet(wrapped_checksum, sizeof(wrapped_checksum), &value) == 0);
    assert(value == 0xFF02);
    assert(parse_packet(too_long, sizeof(too_long), &value) == -1);
    return 0;
}
