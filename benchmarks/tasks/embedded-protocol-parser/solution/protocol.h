/**
 * protocol.h - UART-style framing protocol with byte stuffing and CRC-16
 *
 * Frame format:
 *   [START] [LEN_LO] [LEN_HI] [escaped payload...] [CRC_LO] [CRC_HI] [END]
 *
 * Byte stuffing (escape mapping):
 *   0x7E (FRAME_START) -> 0x7B 0x5E
 *   0x7D (FRAME_END)   -> 0x7B 0x5D
 *   0x7B (ESCAPE)      -> 0x7B 0x5A
 *
 * CRC: CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no final XOR)
 */

#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>
#include <stddef.h>

/* ---- Protocol constants ---- */
#define FRAME_START   0x7E
#define FRAME_END     0x7D
#define ESCAPE        0x7B
#define ESCAPE_XOR    0x20

#define PROTO_MAX_PAYLOAD 256

/* Worst-case frame: START + LEN_LO + LEN_HI + (payload*2) + CRC_LO + CRC_HI + END */
#define PROTO_MAX_FRAME   (3 + (PROTO_MAX_PAYLOAD * 2) + 2 + 1)

/* ---- Error codes ---- */
typedef enum {
    PROTO_OK              =  0,
    PROTO_ERR_NULL_PTR    = -1,
    PROTO_ERR_BUF_TOO_SM  = -2,
    PROTO_ERR_BAD_FRAME   = -3,
    PROTO_ERR_CRC         = -4,
    PROTO_ERR_PAYLOAD_LEN = -5,
    PROTO_ERR_INCOMPLETE  = -6
} proto_err_t;

/* ---- Batch encode / decode ---- */

/**
 * Compute CRC-16/CCITT-FALSE over a buffer.
 * @param data  Input data (must not be NULL if len > 0).
 * @param len   Number of bytes.
 * @return 16-bit CRC value.
 */
uint16_t crc16_ccitt(const uint8_t *data, size_t len);

/**
 * Encode a payload into a framed packet with byte stuffing and CRC.
 *
 * @param payload      Payload bytes (may be NULL if payload_len == 0).
 * @param payload_len  Payload length (0..PROTO_MAX_PAYLOAD).
 * @param out_buf      Output buffer for the complete frame.
 * @param out_buf_len  Size of out_buf.
 * @param out_frame_len  Receives actual frame length written.
 * @return PROTO_OK or negative error code.
 */
proto_err_t protocol_encode(const uint8_t *payload, size_t payload_len,
                            uint8_t *out_buf, size_t out_buf_len,
                            size_t *out_frame_len);

/**
 * Decode a framed packet: unstuff bytes, verify CRC, extract payload.
 *
 * @param frame           Complete frame bytes (from START to END inclusive).
 * @param frame_len       Length of frame.
 * @param out_payload     Buffer for decoded payload.
 * @param out_payload_len Size of out_payload.
 * @param out_actual_len  Receives actual payload length.
 * @return PROTO_OK or negative error code.
 */
proto_err_t protocol_decode(const uint8_t *frame, size_t frame_len,
                            uint8_t *out_payload, size_t out_payload_len,
                            size_t *out_actual_len);

/* ---- Streaming (byte-at-a-time) parser ---- */

typedef enum {
    STATE_IDLE,
    STATE_LEN_LO,
    STATE_LEN_HI,
    STATE_DATA,
    STATE_DATA_ESC,
    STATE_CRC_LO,
    STATE_CRC_HI,
    STATE_DONE
} parser_state_t;

typedef struct {
    parser_state_t state;
    uint8_t  buf[PROTO_MAX_PAYLOAD];   /* decoded payload buffer */
    size_t   buf_idx;                   /* current write position */
    size_t   expected_len;              /* payload length from header */
    uint16_t crc;                       /* running CRC accumulator */
    uint8_t  crc_lo;                    /* received CRC low byte */
    uint8_t  last_byte;                 /* for detecting frame boundaries */
    int      error;                     /* sticky error code */
} protocol_parser_t;

/**
 * Initialise a stream parser to its default state.
 */
void protocol_init(protocol_parser_t *parser);

/**
 * Feed one received byte into the stream parser.
 *
 * @param parser  Initialised parser context.
 * @param byte    Next byte from the UART RX register.
 * @return PROTO_OK while parsing, PROTO_ERR_INCOMPLETE while mid-frame,
 *         PROTO_OK when a complete frame has been received (check parser->error
 *         for CRC / format errors), or a negative error on fatal conditions.
 */
proto_err_t protocol_feed_byte(protocol_parser_t *parser, uint8_t byte);

#endif /* PROTOCOL_H */
