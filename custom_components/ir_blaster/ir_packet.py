"""IR packet builder for Tuya MCU serial protocol.

Confirmed working from UART analysis:
  Single SerialSend5 with DP7 raw code packet fires IR.
  Header: 55 AA 00 06 00 54 07 00 00 50
  Followed by 80 bytes of IR code
  Followed by checksum byte
"""

from __future__ import annotations

# DP7 header: cmd 06, DP7 raw, length 0x0054, data length 0x0050 (80 bytes)
_DP7_HEADER = bytes([0x55, 0xAA, 0x00, 0x06, 0x00, 0x54, 0x07, 0x00, 0x00, 0x50])


def build_send_payload(hex_code: str) -> str | None:
    """Build the single SerialSend5 payload for a given IR hex code.

    Strips 0x prefix if present. Returns full hex string with checksum,
    or None if hex_code is invalid.
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
