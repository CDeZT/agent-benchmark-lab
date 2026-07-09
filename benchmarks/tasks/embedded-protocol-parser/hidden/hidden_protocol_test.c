/**
 * hidden_protocol_test.c - Thorough tests for the protocol parser
 *
 * These tests exercise edge cases and are used for final scoring.
 * The workspace test_protocol.c contains only basic smoke tests.
 */

#include "protocol.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static int tests_run    = 0;
static int tests_passed = 0;

#define TEST(name) do { \
    tests_run++; \
    printf("  %-60s ", name); \
} while (0)

#define PASS() do { tests_passed++; printf("[PASS]\n"); } while (0)
#define FAIL(msg) do { printf("[FAIL] %s\n", msg); } while (0)

/* ====================================================================
 * CRC tests
 * ==================================================================== */

static void test_crc_123456789(void)
{
    /* Well-known test vector: CRC-16/CCITT-FALSE of "123456789" = 0x29B1 */
    TEST("CRC: '123456789' -> 0x29B1");
    const uint8_t data[] = "123456789";
    uint16_t crc = crc16_ccitt(data, 9);
    if (crc == 0x29B1) { PASS(); }
    else { char m[64]; snprintf(m, sizeof(m), "got 0x%04X", crc); FAIL(m); }
}

static void test_crc_empty(void)
{
    TEST("CRC: empty -> 0xFFFF");
    uint16_t crc = crc16_ccitt(NULL, 0);
    if (crc == 0xFFFF) { PASS(); }
    else { char m[64]; snprintf(m, sizeof(m), "got 0x%04X", crc); FAIL(m); }
}

static void test_crc_single_byte(void)
{
    /* CRC-16/CCITT-FALSE of {0x00} */
    TEST("CRC: single byte 0x00 -> 0xE1F0");
    const uint8_t data[] = {0x00};
    uint16_t crc = crc16_ccitt(data, 1);
    if (crc == 0xE1F0) { PASS(); }
    else { char m[64]; snprintf(m, sizeof(m), "got 0x%04X", crc); FAIL(m); }
}

static void test_crc_ff_byte(void)
{
    /* CRC-16/CCITT-FALSE of {0xFF} */
    TEST("CRC: single byte 0xFF -> 0xFF00");
    const uint8_t data[] = {0xFF};
    uint16_t crc = crc16_ccitt(data, 1);
    if (crc == 0xFF00) { PASS(); }
    else { char m[64]; snprintf(m, sizeof(m), "got 0x%04X", crc); FAIL(m); }
}

/* ====================================================================
 * Encode tests
 * ==================================================================== */

static void test_encode_zero_length(void)
{
    TEST("Encode: zero-length payload");
    uint8_t frame[PROTO_MAX_FRAME];
    size_t flen = 0;
    proto_err_t rc = protocol_encode(NULL, 0, frame, sizeof(frame), &flen);
    /* Expected frame: START + LEN(0,0) + CRC(0xFFFF) + END = 6 bytes */
    if (rc == PROTO_OK && flen == 6) { PASS(); }
    else { char m[64]; snprintf(m, sizeof(m), "rc=%d flen=%zu", rc, flen); FAIL(m); }
}

static void test_encode_buf_too_small(void)
{
    TEST("Encode: out_buf too small returns error");
    uint8_t payload[] = {0x41, 0x42, 0x43};
    uint8_t tiny[4];  /* far too small */
    size_t flen = 0;
    proto_err_t rc = protocol_encode(payload, sizeof(payload), tiny, sizeof(tiny), &flen);
    if (rc == PROTO_ERR_BUF_TOO_SM) { PASS(); }
    else { FAIL("expected PROTO_ERR_BUF_TOO_SM"); }
}

static void test_encode_null_checks(void)
{
    TEST("Encode: NULL out_buf returns error");
    uint8_t payload[] = {0x01};
    proto_err_t rc = protocol_encode(payload, 1, NULL, 0, NULL);
    if (rc == PROTO_ERR_NULL_PTR) { PASS(); }
    else { FAIL("expected PROTO_ERR_NULL_PTR"); }
}

static void test_encode_max_payload(void)
{
    TEST("Encode: max payload (256 bytes) succeeds");
    uint8_t payload[PROTO_MAX_PAYLOAD];
    memset(payload, 0xAB, sizeof(payload));
    uint8_t frame[PROTO_MAX_FRAME];
    size_t flen = 0;
    proto_err_t rc = protocol_encode(payload, sizeof(payload), frame, sizeof(frame), &flen);
    if (rc == PROTO_OK && flen > 0) { PASS(); }
    else { FAIL("encode failed for max payload"); }
}

/* ====================================================================
 * Decode tests
 * ==================================================================== */

static void test_decode_roundtrip_simple(void)
{
    TEST("Decode: round-trip with simple payload");
    const uint8_t payload[] = {0x01, 0x02, 0x03};
    uint8_t frame[PROTO_MAX_FRAME];
    size_t flen = 0;
    protocol_encode(payload, sizeof(payload), frame, sizeof(frame), &flen);

    uint8_t out[16];
    size_t olen = 0;
    proto_err_t rc = protocol_decode(frame, flen, out, sizeof(out), &olen);
    if (rc == PROTO_OK && olen == sizeof(payload) && memcmp(out, payload, sizeof(payload)) == 0) {
        PASS();
    } else {
        FAIL("round-trip mismatch");
    }
}

static void test_decode_roundtrip_all_special_bytes(void)
{
    TEST("Decode: round-trip with all special bytes");
    const uint8_t payload[] = {FRAME_START, FRAME_END, ESCAPE, 0x00, 0xFF};
    uint8_t frame[PROTO_MAX_FRAME];
    size_t flen = 0;
    protocol_encode(payload, sizeof(payload), frame, sizeof(frame), &flen);

    uint8_t out[16];
    size_t olen = 0;
    proto_err_t rc = protocol_decode(frame, flen, out, sizeof(out), &olen);
    if (rc == PROTO_OK && olen == sizeof(payload) && memcmp(out, payload, sizeof(payload)) == 0) {
        PASS();
    } else {
        FAIL("special bytes mismatch");
    }
}

static void test_decode_roundtrip_zero_length(void)
{
    TEST("Decode: round-trip with zero-length payload");
    uint8_t frame[PROTO_MAX_FRAME];
    size_t flen = 0;
    protocol_encode(NULL, 0, frame, sizeof(frame), &flen);

    uint8_t out[16];
    size_t olen = 99;
    proto_err_t rc = protocol_decode(frame, flen, out, sizeof(out), &olen);
    if (rc == PROTO_OK && olen == 0) { PASS(); }
    else { FAIL("zero-length round-trip failed"); }
}

static void test_decode_crc_error(void)
{
    TEST("Decode: CRC error detected");
    const uint8_t payload[] = {0xDE, 0xAD};
    uint8_t frame[PROTO_MAX_FRAME];
    size_t flen = 0;
    protocol_encode(payload, sizeof(payload), frame, sizeof(frame), &flen);

    /* Corrupt the CRC low byte */
    frame[flen - 3] ^= 0x01;

    uint8_t out[16];
    size_t olen = 0;
    proto_err_t rc = protocol_decode(frame, flen, out, sizeof(out), &olen);
    if (rc == PROTO_ERR_CRC) { PASS(); }
    else { FAIL("expected PROTO_ERR_CRC"); }
}

static void test_decode_bad_start(void)
{
    TEST("Decode: bad start byte rejected");
    const uint8_t bad[] = {0x00, 0x00, 0x00, 0x00, 0x00, FRAME_END};
    uint8_t out[8];
    size_t olen = 0;
    proto_err_t rc = protocol_decode(bad, sizeof(bad), out, sizeof(out), &olen);
    if (rc == PROTO_ERR_BAD_FRAME) { PASS(); }
    else { FAIL("expected PROTO_ERR_BAD_FRAME"); }
}

static void test_decode_bad_end(void)
{
    TEST("Decode: bad end byte rejected");
    const uint8_t bad[] = {FRAME_START, 0x00, 0x00, 0x00, 0x00, 0x00};
    uint8_t out[8];
    size_t olen = 0;
    proto_err_t rc = protocol_decode(bad, sizeof(bad), out, sizeof(out), &olen);
    if (rc == PROTO_ERR_BAD_FRAME) { PASS(); }
    else { FAIL("expected PROTO_ERR_BAD_FRAME"); }
}

static void test_decode_truncated(void)
{
    TEST("Decode: truncated frame rejected");
    /* Only 3 bytes, below minimum of 6 */
    const uint8_t short_frame[] = {FRAME_START, 0x01, 0x00};
    uint8_t out[8];
    size_t olen = 0;
    proto_err_t rc = protocol_decode(short_frame, sizeof(short_frame), out, sizeof(out), &olen);
    if (rc == PROTO_ERR_BAD_FRAME) { PASS(); }
    else { FAIL("expected PROTO_ERR_BAD_FRAME"); }
}

static void test_decode_out_buf_too_small(void)
{
    TEST("Decode: output buffer too small");
    const uint8_t payload[] = {0x41, 0x42, 0x43, 0x44, 0x45};
    uint8_t frame[PROTO_MAX_FRAME];
    size_t flen = 0;
    protocol_encode(payload, sizeof(payload), frame, sizeof(frame), &flen);

    uint8_t tiny[2];
    size_t olen = 0;
    proto_err_t rc = protocol_decode(frame, flen, tiny, sizeof(tiny), &olen);
    if (rc == PROTO_ERR_BUF_TOO_SM) { PASS(); }
    else { FAIL("expected PROTO_ERR_BUF_TOO_SM"); }
}

static void test_decode_null_pointers(void)
{
    TEST("Decode: NULL pointers return error");
    uint8_t out[8];
    size_t olen = 0;
    proto_err_t rc = protocol_decode(NULL, 10, out, sizeof(out), &olen);
    if (rc == PROTO_ERR_NULL_PTR) { PASS(); }
    else { FAIL("expected PROTO_ERR_NULL_PTR on frame"); }
}

/* ====================================================================
 * Streaming parser tests
 * ==================================================================== */

static void test_stream_basic(void)
{
    TEST("Stream: basic frame fed byte-by-byte");
    const uint8_t payload[] = {0xCA, 0xFE};
    uint8_t frame[PROTO_MAX_FRAME];
    size_t flen = 0;
    protocol_encode(payload, sizeof(payload), frame, sizeof(frame), &flen);

    protocol_parser_t parser;
    protocol_init(&parser);

    proto_err_t last = PROTO_ERR_INCOMPLETE;
    for (size_t i = 0; i < flen; i++) {
        last = protocol_feed_byte(&parser, frame[i]);
    }

    /* After the last byte (END), feed_byte should return PROTO_OK */
    /* But since END is the last byte, the PROTO_OK comes from feeding it */
    /* Let's re-check: the DONE state needs END; after END we get PROTO_OK */
    /* Actually we need to feed END as a separate step in the loop above. */
    /* The loop already feeds all bytes including END, so last should be PROTO_OK. */

    if (last == PROTO_OK
        && parser.error == PROTO_OK
        && parser.buf_idx == sizeof(payload)
        && memcmp(parser.buf, payload, sizeof(payload)) == 0)
    {
        PASS();
    } else {
        char m[80];
        snprintf(m, sizeof(m), "last=%d err=%d idx=%zu", last, parser.error, parser.buf_idx);
        FAIL(m);
    }
}

static void test_stream_garbage_before_frame(void)
{
    TEST("Stream: garbage bytes before frame ignored");
    const uint8_t payload[] = {0x42};
    uint8_t frame[PROTO_MAX_FRAME];
    size_t flen = 0;
    protocol_encode(payload, sizeof(payload), frame, sizeof(frame), &flen);

    protocol_parser_t parser;
    protocol_init(&parser);

    /* Feed some garbage */
    protocol_feed_byte(&parser, 0x12);
    protocol_feed_byte(&parser, 0x34);
    protocol_feed_byte(&parser, 0x56);

    /* Now feed the real frame */
    proto_err_t last = PROTO_ERR_INCOMPLETE;
    for (size_t i = 0; i < flen; i++) {
        last = protocol_feed_byte(&parser, frame[i]);
    }

    if (last == PROTO_OK && parser.error == PROTO_OK
        && parser.buf_idx == 1 && parser.buf[0] == 0x42)
    {
        PASS();
    } else {
        FAIL("garbage handling failed");
    }
}

static void test_stream_crc_error(void)
{
    TEST("Stream: CRC error detected in stream parser");
    const uint8_t payload[] = {0xAA};
    uint8_t frame[PROTO_MAX_FRAME];
    size_t flen = 0;
    protocol_encode(payload, sizeof(payload), frame, sizeof(frame), &flen);

    /* Corrupt CRC low byte */
    frame[flen - 3] ^= 0xFF;

    protocol_parser_t parser;
    protocol_init(&parser);

    for (size_t i = 0; i < flen; i++) {
        protocol_feed_byte(&parser, frame[i]);
    }

    if (parser.error == PROTO_ERR_CRC) { PASS(); }
    else { char m[64]; snprintf(m, sizeof(m), "err=%d", parser.error); FAIL(m); }
}

static void test_stream_zero_length(void)
{
    TEST("Stream: zero-length payload");
    uint8_t frame[PROTO_MAX_FRAME];
    size_t flen = 0;
    protocol_encode(NULL, 0, frame, sizeof(frame), &flen);

    protocol_parser_t parser;
    protocol_init(&parser);

    proto_err_t last = PROTO_ERR_INCOMPLETE;
    for (size_t i = 0; i < flen; i++) {
        last = protocol_feed_byte(&parser, frame[i]);
    }

    if (last == PROTO_OK && parser.error == PROTO_OK && parser.buf_idx == 0) {
        PASS();
    } else {
        FAIL("zero-length stream failed");
    }
}

static void test_stream_two_frames_back_to_back(void)
{
    TEST("Stream: two frames parsed sequentially");
    const uint8_t p1[] = {0x11};
    const uint8_t p2[] = {0x22, 0x33};
    uint8_t f1[PROTO_MAX_FRAME], f2[PROTO_MAX_FRAME];
    size_t l1 = 0, l2 = 0;
    protocol_encode(p1, sizeof(p1), f1, sizeof(f1), &l1);
    protocol_encode(p2, sizeof(p2), f2, sizeof(f2), &l2);

    protocol_parser_t parser;
    protocol_init(&parser);

    /* Feed first frame */
    proto_err_t last = PROTO_ERR_INCOMPLETE;
    for (size_t i = 0; i < l1; i++) {
        last = protocol_feed_byte(&parser, f1[i]);
    }
    int ok1 = (last == PROTO_OK && parser.error == PROTO_OK
               && parser.buf_idx == 1 && parser.buf[0] == 0x11);

    /* Feed second frame */
    last = PROTO_ERR_INCOMPLETE;
    for (size_t i = 0; i < l2; i++) {
        last = protocol_feed_byte(&parser, f2[i]);
    }
    int ok2 = (last == PROTO_OK && parser.error == PROTO_OK
               && parser.buf_idx == 2 && parser.buf[0] == 0x22 && parser.buf[1] == 0x33);

    if (ok1 && ok2) { PASS(); }
    else { FAIL("back-to-back parsing failed"); }
}

/* ====================================================================
 * main
 * ==================================================================== */

int main(void)
{
    printf("=== Protocol Parser Hidden Tests ===\n\n");

    /* CRC */
    test_crc_123456789();
    test_crc_empty();
    test_crc_single_byte();
    test_crc_ff_byte();

    /* Encode */
    test_encode_zero_length();
    test_encode_buf_too_small();
    test_encode_null_checks();
    test_encode_max_payload();

    /* Decode */
    test_decode_roundtrip_simple();
    test_decode_roundtrip_all_special_bytes();
    test_decode_roundtrip_zero_length();
    test_decode_crc_error();
    test_decode_bad_start();
    test_decode_bad_end();
    test_decode_truncated();
    test_decode_out_buf_too_small();
    test_decode_null_pointers();

    /* Streaming */
    test_stream_basic();
    test_stream_garbage_before_frame();
    test_stream_crc_error();
    test_stream_zero_length();
    test_stream_two_frames_back_to_back();

    printf("\n%d / %d tests passed\n", tests_passed, tests_run);
    return (tests_passed == tests_run) ? 0 : 1;
}
