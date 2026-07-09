/**
 * test_protocol.c - Public tests for the protocol parser
 *
 * These tests verify basic functionality. The hidden tests are more thorough.
 */

#include "protocol.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>

static int tests_run    = 0;
static int tests_passed = 0;

#define TEST(name) do { \
    tests_run++; \
    printf("  %-50s ", name); \
} while (0)

#define PASS() do { tests_passed++; printf("[PASS]\n"); } while (0)
#define FAIL(msg) do { printf("[FAIL] %s\n", msg); } while (0)

/* ---- CRC tests ---- */

static void test_crc_known_value(void)
{
    /* CRC-16/CCITT-FALSE of "123456789" = 0x29B1 */
    TEST("CRC-16/CCITT-FALSE of '123456789'");
    const uint8_t data[] = "123456789";
    uint16_t crc = crc16_ccitt(data, 9);
    if (crc == 0x29B1) {
        PASS();
    } else {
        char msg[64];
        snprintf(msg, sizeof(msg), "expected 0x29B1, got 0x%04X", crc);
        FAIL(msg);
    }
}

static void test_crc_empty(void)
{
    /* CRC-16/CCITT-FALSE of empty input = init value 0xFFFF */
    TEST("CRC-16/CCITT-FALSE of empty input");
    uint16_t crc = crc16_ccitt(NULL, 0);
    if (crc == 0xFFFF) {
        PASS();
    } else {
        char msg[64];
        snprintf(msg, sizeof(msg), "expected 0xFFFF, got 0x%04X", crc);
        FAIL(msg);
    }
}

/* ---- Encode / decode round-trip ---- */

static void test_roundtrip(void)
{
    TEST("Encode/decode round-trip");
    const uint8_t payload[] = {0x01, 0x02, 0x03, 0x04, 0x05};
    uint8_t frame[PROTO_MAX_FRAME];
    size_t frame_len = 0;

    proto_err_t rc = protocol_encode(payload, sizeof(payload),
                                     frame, sizeof(frame), &frame_len);
    if (rc != PROTO_OK) {
        FAIL("encode failed");
        return;
    }

    uint8_t decoded[PROTO_MAX_PAYLOAD];
    size_t decoded_len = 0;
    rc = protocol_decode(frame, frame_len, decoded, sizeof(decoded), &decoded_len);
    if (rc != PROTO_OK) {
        FAIL("decode failed");
        return;
    }

    if (decoded_len != sizeof(payload) || memcmp(decoded, payload, sizeof(payload)) != 0) {
        FAIL("payload mismatch");
        return;
    }
    PASS();
}

static void test_roundtrip_with_special_bytes(void)
{
    TEST("Round-trip with special bytes in payload");
    /* Include all three special bytes: START, END, ESCAPE */
    const uint8_t payload[] = {FRAME_START, 0x10, FRAME_END, 0x20, ESCAPE, 0x30};
    uint8_t frame[PROTO_MAX_FRAME];
    size_t frame_len = 0;

    proto_err_t rc = protocol_encode(payload, sizeof(payload),
                                     frame, sizeof(frame), &frame_len);
    if (rc != PROTO_OK) {
        FAIL("encode failed");
        return;
    }

    uint8_t decoded[PROTO_MAX_PAYLOAD];
    size_t decoded_len = 0;
    rc = protocol_decode(frame, frame_len, decoded, sizeof(decoded), &decoded_len);
    if (rc != PROTO_OK) {
        FAIL("decode failed");
        return;
    }

    if (decoded_len != sizeof(payload) || memcmp(decoded, payload, sizeof(payload)) != 0) {
        FAIL("payload mismatch");
        return;
    }
    PASS();
}

/* ---- Decode error cases ---- */

static void test_decode_bad_start(void)
{
    TEST("Decode rejects bad start byte");
    const uint8_t bad_frame[] = {0x00, 0x01, 0x00, 0xAA, 0xBB, 0xCC, FRAME_END};
    uint8_t out[16];
    size_t out_len = 0;
    proto_err_t rc = protocol_decode(bad_frame, sizeof(bad_frame), out, sizeof(out), &out_len);
    if (rc == PROTO_ERR_BAD_FRAME) {
        PASS();
    } else {
        FAIL("expected PROTO_ERR_BAD_FRAME");
    }
}

static void test_decode_crc_error(void)
{
    TEST("Decode detects CRC error");
    /* Encode a payload, then corrupt one byte in the CRC area */
    const uint8_t payload[] = {0x42};
    uint8_t frame[PROTO_MAX_FRAME];
    size_t frame_len = 0;
    protocol_encode(payload, sizeof(payload), frame, sizeof(frame), &frame_len);

    /* Corrupt the CRC low byte (second to last byte before END) */
    frame[frame_len - 3] ^= 0xFF;

    uint8_t out[16];
    size_t out_len = 0;
    proto_err_t rc = protocol_decode(frame, frame_len, out, sizeof(out), &out_len);
    if (rc == PROTO_ERR_CRC) {
        PASS();
    } else {
        FAIL("expected PROTO_ERR_CRC");
    }
}

static void test_encode_max_payload(void)
{
    TEST("Encode maximum-length payload");
    uint8_t payload[PROTO_MAX_PAYLOAD];
    memset(payload, 0xAB, sizeof(payload));

    uint8_t frame[PROTO_MAX_FRAME];
    size_t frame_len = 0;
    proto_err_t rc = protocol_encode(payload, sizeof(payload),
                                     frame, sizeof(frame), &frame_len);
    if (rc == PROTO_OK && frame_len > 0) {
        PASS();
    } else {
        FAIL("encode failed for max payload");
    }
}

static void test_null_pointer_handling(void)
{
    TEST("NULL pointer returns error");
    proto_err_t rc = protocol_encode(NULL, 5, NULL, 0, NULL);
    if (rc == PROTO_ERR_NULL_PTR) {
        PASS();
    } else {
        FAIL("expected PROTO_ERR_NULL_PTR");
    }
}

int main(void)
{
    printf("=== Protocol Parser Public Tests ===\n");

    test_crc_known_value();
    test_crc_empty();
    test_roundtrip();
    test_roundtrip_with_special_bytes();
    test_decode_bad_start();
    test_decode_crc_error();
    test_encode_max_payload();
    test_null_pointer_handling();

    printf("\n%d / %d tests passed\n", tests_passed, tests_run);
    return (tests_passed == tests_run) ? 0 : 1;
}
