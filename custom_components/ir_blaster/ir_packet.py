"""IR packet builder for Tuya MCU serial protocol."""

from __future__ import annotations


# Packet 1: DP1 enum=0 (send_ir trigger) — fixed, checksum pre-verified
TRIGGER_PACKET = "55AA000600050104000100 0C"

# DP7 header: 55 AA 00 06 00 54 07 00 00 50
_DP7_HEADER = bytes([0x55, 0xAA, 0x00, 0x06, 0x00, 0x54, 0x07, 0x00, 0x00, 0x50])


def build_code_packet(hex_code: str) -> str | None:
    """Build the DP7 SerialSend5 payload for a given hex code string.

    Returns the full hex string with checksum, or None if hex_code is invalid.
    """
    if not hex_code:
        return None
    clean = hex_code[2:] if hex_code.startswith("0x") else hex_code
    try:
        code_bytes = bytes.fromhex(clean)
    except ValueError:
        return None

    pkt = _DP7_HEADER + code_bytes
    checksum = sum(pkt) & 0xFF
    return pkt.hex().upper() + f"{checksum:02X}"
