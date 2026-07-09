/**
 * protocol.c - UART-style framing protocol with byte stuffing and CRC-16
 *
 * Reference implementation. See protocol.h for the specification.
 *
 * Design notes:
 *  - CRC-16/CCITT-FALSE is computed over the *raw* (unstuffed) payload only,
 *    not over the length field or framing bytes.
 *  - Byte stuffing is symmetrical: both encode and decode use the same
 *    escape mapping (XOR with 0x20).
 *  - The streaming parser accumulates CRC incrementally as payload bytes
 *    are decoded, so the final comparison is a simple equality check.
 *  - All public functions perform NULL-pointer checks before dereferencing,
 *    and all buffer writes are bounds-checked.
 */

#include "protocol.h"
#include <string.h>

/* ================================================================
 * CRC-16/CCITT-FALSE
 *
 * Poly:  0x1021
 * Init:  0xFFFF
 * XOR-out: none (raw result)
 * ================================================================ */

uint16_t crc16_ccitt(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFF;

    if (data == NULL || len == 0) {
        return crc;
    }

    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int j = 0; j < 8; j++) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

/* ================================================================
 * Byte-stuffing helpers (internal)
 * ================================================================ */

/**
 * Append one byte to the output buffer.
 * Returns 1 on success, 0 if the buffer is full.
 */
static int buf_put(uint8_t *buf, size_t cap, size_t *pos, uint8_t byte)
{
    if (*pos >= cap) {
        return 0;
    }
    buf[(*pos)++] = byte;
    return 1;
}

/**
 * Stuff one payload byte into the output buffer.
 *
 * The three protocol-significant bytes are escaped:
 *   FRAME_START (0x7E) -> ESCAPE (0x7B) + (0x7E ^ 0x20 = 0x5E)
 *   FRAME_END   (0x7D) -> ESCAPE (0x7B) + (0x7D ^ 0x20 = 0x5D)
 *   ESCAPE      (0x7B) -> ESCAPE (0x7B) + (0x7B ^ 0x20 = 0x5A)
 *
 * Returns 1 on success, 0 on buffer overflow.
 */
static int stuff_byte(uint8_t *buf, size_t cap, size_t *pos, uint8_t byte)
{
    if (byte == FRAME_START || byte == FRAME_END || byte == ESCAPE) {
        if (!buf_put(buf, cap, pos, ESCAPE)) return 0;
        return buf_put(buf, cap, pos, byte ^ ESCAPE_XOR);
    }
    return buf_put(buf, cap, pos, byte);
}

/* ================================================================
 * Encode
 *
 * Frame layout (after encoding):
 *   [FRAME_START] [LEN_LO] [LEN_HI] [stuffed payload...] [CRC_LO] [CRC_HI] [FRAME_END]
 *
 * CRC is computed over the *raw* payload before stuffing.
 * ================================================================ */

proto_err_t protocol_encode(const uint8_t *payload, size_t payload_len,
                            uint8_t *out_buf, size_t out_buf_len,
                            size_t *out_frame_len)
{
    /* NULL-pointer checks on all pointer arguments */
    if (out_buf == NULL || out_frame_len == NULL) {
        return PROTO_ERR_NULL_PTR;
    }
    if (payload == NULL && payload_len > 0) {
        return PROTO_ERR_NULL_PTR;
    }
    if (payload_len > PROTO_MAX_PAYLOAD) {
        return PROTO_ERR_PAYLOAD_LEN;
    }

    size_t pos = 0;

    /* Start marker */
    if (!buf_put(out_buf, out_buf_len, &pos, FRAME_START)) {
        return PROTO_ERR_BUF_TOO_SM;
    }

    /* Length (little-endian, 16 bits) */
    if (!buf_put(out_buf, out_buf_len, &pos, (uint8_t)(payload_len & 0xFF))) {
        return PROTO_ERR_BUF_TOO_SM;
    }
    if (!buf_put(out_buf, out_buf_len, &pos, (uint8_t)((payload_len >> 8) & 0xFF))) {
        return PROTO_ERR_BUF_TOO_SM;
    }

    /* Escaped payload */
    for (size_t i = 0; i < payload_len; i++) {
        if (!stuff_byte(out_buf, out_buf_len, &pos, payload[i])) {
            return PROTO_ERR_BUF_TOO_SM;
        }
    }

    /* CRC-16 over raw payload (little-endian) */
    uint16_t crc = crc16_ccitt(payload, payload_len);
    if (!buf_put(out_buf, out_buf_len, &pos, (uint8_t)(crc & 0xFF))) {
        return PROTO_ERR_BUF_TOO_SM;
    }
    if (!buf_put(out_buf, out_buf_len, &pos, (uint8_t)((crc >> 8) & 0xFF))) {
        return PROTO_ERR_BUF_TOO_SM;
    }

    /* End marker */
    if (!buf_put(out_buf, out_buf_len, &pos, FRAME_END)) {
        return PROTO_ERR_BUF_TOO_SM;
    }

    *out_frame_len = pos;
    return PROTO_OK;
}

/* ================================================================
 * Decode (batch)
 *
 * The frame has already been assembled (START..END inclusive).
 * We extract the length, unstuff the payload, verify the CRC.
 * ================================================================ */

proto_err_t protocol_decode(const uint8_t *frame, size_t frame_len,
                            uint8_t *out_payload, size_t out_payload_len,
                            size_t *out_actual_len)
{
    if (frame == NULL || out_payload == NULL || out_actual_len == NULL) {
        return PROTO_ERR_NULL_PTR;
    }

    /* Minimum frame: START(1) + LEN(2) + CRC(2) + END(1) = 6
     * (zero-length payload has no payload bytes, but CRC is still present) */
    if (frame_len < 6) {
        return PROTO_ERR_BAD_FRAME;
    }
    if (frame[0] != FRAME_START) {
        return PROTO_ERR_BAD_FRAME;
    }
    if (frame[frame_len - 1] != FRAME_END) {
        return PROTO_ERR_BAD_FRAME;
    }

    /* Parse declared payload length */
    size_t payload_len = (size_t)frame[1] | ((size_t)frame[2] << 8);
    if (payload_len > PROTO_MAX_PAYLOAD) {
        return PROTO_ERR_PAYLOAD_LEN;
    }
    if (out_payload_len < payload_len) {
        return PROTO_ERR_BUF_TOO_SM;
    }

    /* Unstuff: raw payload bytes occupy positions 3..(frame_len-4) inclusive
     * (subtract START + 2 LEN + 2 CRC + END = 6 bytes from total) */
    size_t raw_region_len = frame_len - 6;
    int escaped = 0;
    size_t dec_idx = 0;

    for (size_t i = 0; i < raw_region_len; i++) {
        uint8_t b = frame[3 + i];

        if (escaped) {
            /* Previous byte was ESCAPE; this byte is XORed to recover original */
            b ^= ESCAPE_XOR;
            escaped = 0;
        } else if (b == ESCAPE) {
            escaped = 1;
            continue;   /* don't store yet; next iteration handles the pair */
        }

        if (dec_idx >= payload_len) {
            /* More decoded bytes than declared length */
            return PROTO_ERR_BAD_FRAME;
        }
        out_payload[dec_idx++] = b;
    }

    if (escaped) {
        /* Trailing ESCAPE with no following byte */
        return PROTO_ERR_BAD_FRAME;
    }
    if (dec_idx != payload_len) {
        return PROTO_ERR_BAD_FRAME;
    }

    /* Verify CRC (little-endian in frame) */
    uint16_t rx_crc = (uint16_t)frame[frame_len - 3]
                    | ((uint16_t)frame[frame_len - 2] << 8);
    uint16_t calc_crc = crc16_ccitt(out_payload, payload_len);
    if (rx_crc != calc_crc) {
        return PROTO_ERR_CRC;
    }

    *out_actual_len = payload_len;
    return PROTO_OK;
}

/* ================================================================
 * Streaming parser
 *
 * State machine:
 *   IDLE  --[START]--> LEN_LO --[b]--> LEN_HI --[b]-->
 *       DATA --[b or ESC]--> DATA_ESC (if ESC received)
 *       ...when buf_idx == expected_len --> CRC_LO --[b]--> CRC_HI --[b]-->
 *       DONE --[END]--> IDLE (success) / error (anything else)
 *
 * The CRC is computed incrementally over decoded payload bytes.
 * ================================================================ */

void protocol_init(protocol_parser_t *parser)
{
    if (parser == NULL) {
        return;
    }
    /* Zero the entire struct to avoid stale data */
    memset(parser, 0, sizeof(*parser));
    parser->state = STATE_IDLE;
    parser->error = PROTO_OK;
}

proto_err_t protocol_feed_byte(protocol_parser_t *parser, uint8_t byte)
{
    if (parser == NULL) {
        return PROTO_ERR_NULL_PTR;
    }

    switch (parser->state) {

    case STATE_IDLE:
        if (byte == FRAME_START) {
            parser->state       = STATE_LEN_LO;
            parser->buf_idx     = 0;
            parser->expected_len = 0;
            parser->crc         = 0xFFFF;
            parser->error       = PROTO_OK;
        }
        break;

    case STATE_LEN_LO:
        parser->expected_len = byte;
        parser->state = STATE_LEN_HI;
        break;

    case STATE_LEN_HI:
        parser->expected_len |= (size_t)byte << 8;
        if (parser->expected_len > PROTO_MAX_PAYLOAD) {
            parser->error = PROTO_ERR_PAYLOAD_LEN;
            parser->state = STATE_IDLE;
            return PROTO_ERR_PAYLOAD_LEN;
        }
        if (parser->expected_len == 0) {
            parser->state = STATE_CRC_LO;
        } else {
            parser->state = STATE_DATA;
        }
        break;

    case STATE_DATA:
        if (byte == ESCAPE) {
            parser->state = STATE_DATA_ESC;
            break;
        }
        /* Bounds check */
        if (parser->buf_idx >= PROTO_MAX_PAYLOAD) {
            parser->error = PROTO_ERR_BUF_TOO_SM;
            parser->state = STATE_IDLE;
            return PROTO_ERR_BUF_TOO_SM;
        }
        /* Store and accumulate CRC */
        parser->buf[parser->buf_idx] = byte;
        parser->crc ^= (uint16_t)byte << 8;
        for (int j = 0; j < 8; j++) {
            parser->crc = (parser->crc & 0x8000)
                        ? (parser->crc << 1) ^ 0x1021
                        : (parser->crc << 1);
        }
        parser->buf_idx++;
        if (parser->buf_idx >= parser->expected_len) {
            parser->state = STATE_CRC_LO;
        }
        break;

    case STATE_DATA_ESC:
        {
            uint8_t decoded = byte ^ ESCAPE_XOR;
            if (parser->buf_idx >= PROTO_MAX_PAYLOAD) {
                parser->error = PROTO_ERR_BUF_TOO_SM;
                parser->state = STATE_IDLE;
                return PROTO_ERR_BUF_TOO_SM;
            }
            parser->buf[parser->buf_idx] = decoded;
            /* Accumulate CRC on the decoded byte */
            parser->crc ^= (uint16_t)decoded << 8;
            for (int j = 0; j < 8; j++) {
                parser->crc = (parser->crc & 0x8000)
                            ? (parser->crc << 1) ^ 0x1021
                            : (parser->crc << 1);
            }
            parser->buf_idx++;
            parser->state = STATE_DATA;
            if (parser->buf_idx >= parser->expected_len) {
                parser->state = STATE_CRC_LO;
            }
        }
        break;

    case STATE_CRC_LO:
        parser->crc_lo = byte;
        parser->state  = STATE_CRC_HI;
        break;

    case STATE_CRC_HI:
        {
            uint16_t rx_crc = (uint16_t)parser->crc_lo | ((uint16_t)byte << 8);
            if (rx_crc != parser->crc) {
                parser->error = PROTO_ERR_CRC;
            }
        }
        parser->state = STATE_DONE;
        break;

    case STATE_DONE:
        if (byte == FRAME_END) {
            parser->state = STATE_IDLE;
            return (parser->error == PROTO_OK) ? PROTO_OK : parser->error;
        }
        parser->error = PROTO_ERR_BAD_FRAME;
        parser->state = STATE_IDLE;
        return PROTO_ERR_BAD_FRAME;

    default:
        parser->state = STATE_IDLE;
        break;
    }

    return PROTO_ERR_INCOMPLETE;
}
