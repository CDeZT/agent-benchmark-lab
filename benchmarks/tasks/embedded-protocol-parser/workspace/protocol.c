/**
 * protocol.c - UART-style framing protocol (BUGGY workspace version)
 *
 * Students: fix the bugs and complete the missing implementations below.
 * See protocol.h for the specification.
 */

#include "protocol.h"
#include <string.h>

/* ================================================================
 * CRC-16/CCITT-FALSE
 *
 * BUG: the polynomial and init value are intentionally wrong.
 * Reference: poly = 0x1021, init = 0xFFFF, no final XOR.
 * ================================================================ */
uint16_t crc16_ccitt(const uint8_t *data, size_t len)
{
    /* BUG: using wrong initial value 0x0000 instead of 0xFFFF */
    uint16_t crc = 0x0000;

    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int j = 0; j < 8; j++) {
            if (crc & 0x8000) {
                /* BUG: wrong polynomial 0x1023 instead of 0x1021 */
                crc = (crc << 1) ^ 0x1023;
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

/* ================================================================
 * Byte stuffing helpers
 * ================================================================ */

/**
 * Append a single byte to the output buffer.
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
 * Stuff a single payload byte into the output buffer.
 * Special bytes are escaped; ordinary bytes are copied verbatim.
 * Returns 1 on success, 0 on buffer overflow.
 */
static int stuff_byte(uint8_t *buf, size_t cap, size_t *pos, uint8_t byte)
{
    if (byte == FRAME_START) {
        if (!buf_put(buf, cap, pos, ESCAPE)) return 0;
        return buf_put(buf, cap, pos, byte ^ ESCAPE_XOR);
    }
    if (byte == FRAME_END) {
        if (!buf_put(buf, cap, pos, ESCAPE)) return 0;
        return buf_put(buf, cap, pos, byte ^ ESCAPE_XOR);
    }
    /* BUG: forgot to escape the ESCAPE byte itself (0x7B) */
    return buf_put(buf, cap, pos, byte);
}

/* ================================================================
 * Encode
 * ================================================================ */

proto_err_t protocol_encode(const uint8_t *payload, size_t payload_len,
                            uint8_t *out_buf, size_t out_buf_len,
                            size_t *out_frame_len)
{
    /* BUG: missing NULL check on out_buf and out_frame_len */
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

    /* Length (little-endian) */
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

    /* CRC over the raw payload */
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

    if (out_frame_len) {
        *out_frame_len = pos;
    }
    return PROTO_OK;
}

/* ================================================================
 * Decode (batch)
 * ================================================================ */

proto_err_t protocol_decode(const uint8_t *frame, size_t frame_len,
                            uint8_t *out_payload, size_t out_payload_len,
                            size_t *out_actual_len)
{
    if (frame == NULL || out_payload == NULL) {
        return PROTO_ERR_NULL_PTR;
    }
    /* Minimum frame: START + LEN_LO + LEN_HI + CRC_LO + CRC_HI + END = 7 */
    if (frame_len < 7) {
        return PROTO_ERR_BAD_FRAME;
    }
    if (frame[0] != FRAME_START) {
        return PROTO_ERR_BAD_FRAME;
    }
    if (frame[frame_len - 1] != FRAME_END) {
        return PROTO_ERR_BAD_FRAME;
    }

    /* Parse length */
    size_t payload_len = (size_t)frame[1] | ((size_t)frame[2] << 8);
    if (payload_len > PROTO_MAX_PAYLOAD) {
        return PROTO_ERR_PAYLOAD_LEN;
    }

    /* Unstuff the payload area (bytes 3 .. frame_len-4) */
    size_t raw_len = frame_len - 6; /* exclude START, LEN_LO, LEN_HI, CRC_LO, CRC_HI, END */
    if (out_payload_len < payload_len) {
        return PROTO_ERR_BUF_TOO_SM;
    }

    int escaped = 0;
    size_t dec_idx = 0;
    for (size_t i = 0; i < raw_len; i++) {
        uint8_t b = frame[3 + i];
        if (b == ESCAPE) {
            escaped = 1;
            continue;
        }
        if (escaped) {
            b ^= ESCAPE_XOR;
            escaped = 0;
        }
        if (dec_idx >= payload_len) {
            /* More decoded bytes than declared length -> bad frame */
            /* BUG: should return error but just silently ignores extra data */
            break;
        }
        out_payload[dec_idx++] = b;
    }

    if (dec_idx != payload_len) {
        return PROTO_ERR_BAD_FRAME;
    }

    /* Extract CRC from frame */
    uint16_t rx_crc = (uint16_t)frame[frame_len - 3]
                    | ((uint16_t)frame[frame_len - 2] << 8);

    /* BUG: CRC verification is commented out -- always passes */
    /* uint16_t calc_crc = crc16_ccitt(out_payload, payload_len);
    if (rx_crc != calc_crc) {
        return PROTO_ERR_CRC;
    } */

    (void)rx_crc; /* suppress unused warning */

    if (out_actual_len) {
        *out_actual_len = payload_len;
    }
    return PROTO_OK;
}

/* ================================================================
 * Streaming parser
 * ================================================================ */

void protocol_init(protocol_parser_t *parser)
{
    /* BUG: does not zero out the entire struct, leaves stale data */
    if (parser) {
        parser->state = STATE_IDLE;
        parser->buf_idx = 0;
        parser->error = PROTO_OK;
    }
}

proto_err_t protocol_feed_byte(protocol_parser_t *parser, uint8_t byte)
{
    if (parser == NULL) {
        return PROTO_ERR_NULL_PTR;
    }

    switch (parser->state) {
    case STATE_IDLE:
        if (byte == FRAME_START) {
            parser->state = STATE_LEN_LO;
            parser->buf_idx = 0;
            parser->expected_len = 0;
            parser->crc = 0xFFFF;   /* NOTE: correct init here, but CRC calc is wrong */
            parser->error = PROTO_OK;
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
        } else {
            if (parser->buf_idx >= PROTO_MAX_PAYLOAD) {
                parser->error = PROTO_ERR_BUF_TOO_SM;
                parser->state = STATE_IDLE;
                return PROTO_ERR_BUF_TOO_SM;
            }
            parser->buf[parser->buf_idx++] = byte;
            /* BUG: not accumulating CRC correctly */
            if (parser->buf_idx >= parser->expected_len) {
                parser->state = STATE_CRC_LO;
            }
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
            parser->buf[parser->buf_idx++] = decoded;
            parser->state = STATE_DATA;
            if (parser->buf_idx >= parser->expected_len) {
                parser->state = STATE_CRC_LO;
            }
        }
        break;

    case STATE_CRC_LO:
        parser->crc_lo = byte;
        parser->state = STATE_CRC_HI;
        break;

    case STATE_CRC_HI:
        {
            uint16_t rx_crc = (uint16_t)parser->crc_lo | ((uint16_t)byte << 8);
            uint16_t calc_crc = crc16_ccitt(parser->buf, parser->expected_len);
            /* BUG: comparison inverted or always passes */
            if (rx_crc == calc_crc) {
                parser->error = PROTO_ERR_CRC;  /* BUG: sets error on good CRC */
            }
        }
        parser->state = STATE_DONE;
        break;

    case STATE_DONE:
        /* Waiting for END marker */
        if (byte == FRAME_END) {
            parser->state = STATE_IDLE;
            return PROTO_OK;
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
