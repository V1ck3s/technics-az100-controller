# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Technics EAH-AZ100 - Full control via Bluetooth RFCOMM (RACE protocol)

Handles ~30 GET/SET commands: ANC, EQ, spatial audio, battery, codec,
multipoint, LED, wearing detection, voice assistant, etc.
"""

import argparse
import json
import socket
import struct
import sys
import time
import winreg

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

RFCOMM_CHANNEL = 21
DEVICE_NAME_PREFIX = "EAH-AZ"


# ---------------------------------------------------------------------------
#  Bluetooth device discovery (Windows registry)
# ---------------------------------------------------------------------------

def discover_device() -> str | None:
    """Find a paired Technics device by scanning the Windows BT registry.

    Looks for paired Bluetooth devices whose name starts with DEVICE_NAME_PREFIX
    (e.g. 'EAH-AZ100'). Returns the MAC address as 'XX:XX:XX:XX:XX:XX' or None.
    """
    bt_key = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices"
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, bt_key)
    except OSError:
        return None
    i = 0
    while True:
        try:
            subkey_name = winreg.EnumKey(root, i)
            i += 1
        except OSError:
            break
        try:
            dev = winreg.OpenKey(root, subkey_name)
            name_bytes, _ = winreg.QueryValueEx(dev, "Name")
            winreg.CloseKey(dev)
            if isinstance(name_bytes, bytes):
                name = name_bytes.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
            else:
                name = str(name_bytes)
            if name.startswith(DEVICE_NAME_PREFIX):
                mac = ":".join(subkey_name[j:j+2] for j in range(0, 12, 2))
                winreg.CloseKey(root)
                return mac
        except OSError:
            continue
    winreg.CloseKey(root)
    return None

# ---------------------------------------------------------------------------
#  Mapping tables  name <-> value
# ---------------------------------------------------------------------------

ANC_MODES = {"off": 0, "nc": 1, "ambient": 2}
ANC_MODES_REV = {0: "Off", 1: "Noise Canceling", 2: "Ambient"}

EQ_MODES = {
    "off": 0, "bass": 1, "clear-voice": 2, "custom": 3,
    "bass2": 4, "clear-voice2": 5, "super-bass": 9,
    "custom2": 10, "custom3": 11,
}
EQ_MODES_REV = {v: k for k, v in EQ_MODES.items()}

MULTIPOINT_MODES = {"off": 0, "on": 1, "triple": 2}
MULTIPOINT_MODES_REV = {0: "off", 1: "on", 2: "triple"}

ONOFF = {"off": 0, "on": 1}
ONOFF_REV = {0: "off", 1: "on"}

ASSISTANT_MODES = {"off": 255, "google": 1, "alexa": 2}
ASSISTANT_MODES_REV = {0: "unset", 1: "google", 2: "alexa", 255: "off"}

NOISE_REDUCTION_MODES = {"normal": 0, "high": 1}
NOISE_REDUCTION_MODES_REV = {0: "normal", 1: "high"}

BUFFER_MODES = {"auto": 0, "music": 1, "video": 2}
BUFFER_MODES_REV = {0: "auto", 1: "music", 2: "video"}

LANGUAGE_MAP = {
    "ja": 0, "en": 1, "de": 2, "fr": 3, "fr-ca": 4,
    "es": 5, "it": 6, "pl": 7, "ru": 8, "uk": 9,
    "zh": 10, "yue": 11,
}
LANGUAGE_MAP_REV = {v: k for k, v in LANGUAGE_MAP.items()}

JMV_MODES = {"off": 0, "on": 1}
JMV_MODES_REV = {0: "off", 1: "on"}

A2DP_CODECS = {"sbc": 1, "aac": 2, "aptx": 3, "aptx-ll": 4, "aptx-hd": 5, "ldac": 6}
A2DP_CODECS_REV = {0: "unknown", 1: "sbc", 2: "aac", 3: "aptx", 4: "aptx-ll", 5: "aptx-hd", 6: "ldac"}

AMBIENT_MODES = {"transparent": 0, "attention": 1}
AMBIENT_MODES_REV = {0: "transparent", 1: "attention"}

MUSIC_MODES = {"play": 0, "stop": 1}
MUSIC_MODES_REV = {0: "play", 1: "stop"}

COLOR_MAP = {
    1: "Blue", 2: "Navy", 4: "Orange", 7: "Green", 8: "Gray",
    11: "Black", 14: "Gold", 16: "Pink", 18: "Red", 19: "Silver",
    20: "Brown", 22: "Violet", 23: "White", 25: "Yellow", 26: "Other",
}

CODEC_TYPES = {
    0: "Unknown", 1: "SBC", 2: "AAC", 3: "aptX",
    4: "aptX LL", 5: "aptX HD", 6: "LDAC",
}

SAMPLE_FREQS = {1: "8 kHz", 8: "44.1 kHz", 9: "48 kHz", 12: "96 kHz"}

CHANNEL_MODES = {1: "Mono", 2: "Dual", 3: "Stereo"}

VP_OUTSIDE_MODES = {"tone": 0, "voice": 1}
VP_OUTSIDE_MODES_REV = {0: "tone", 1: "voice"}

VP_CONNECTED_MODES = {
    0: "Connected", 1: "Notification sound", 2: "Smart Phone",
    3: "Computer", 4: "Audio Player", 5: "Smart Phone 2",
    6: "Tablet", 7: "Device",
}

TOGGLE_BITS = {"off": 1, "nc": 2, "ambient": 4}
TOGGLE_BITS_REV = {1: "off", 2: "nc", 4: "ambient"}

# Mapping NC Adjust level <-> dB
NC_ADJUST_DB = {}
for _v in range(20, 41):
    NC_ADJUST_DB[_v] = (_v - 32) * 0.5
NC_ADJUST_DB[0] = None  # default
NC_ADJUST_DB_REV = {db: v for v, db in NC_ADJUST_DB.items() if db is not None}

# ---------------------------------------------------------------------------
#  Generic command registry (GET/SET 1 byte)
# ---------------------------------------------------------------------------

class CmdDef:
    __slots__ = ("name", "get_id", "set_id", "field", "values", "values_rev")

    def __init__(self, name, get_id, set_id, field, values, values_rev):
        self.name = name
        self.get_id = get_id
        self.set_id = set_id
        self.field = field
        self.values = values
        self.values_rev = values_rev


GENERIC_CMDS: dict[str, CmdDef] = {}

def _reg(name, get_id, set_id, field, values, values_rev):
    GENERIC_CMDS[name] = CmdDef(name, get_id, set_id, field, values, values_rev)

# EQ uses Airoha PEQ commands (0x0901/0x0900), not Panasonic cmds 12/13
_reg("led",              19, 20, "mode",             ONOFF,                 ONOFF_REV)
_reg("multipoint",       50, 51, "mode",             MULTIPOINT_MODES,      MULTIPOINT_MODES_REV)
_reg("adaptive-anc",    103,104, "mode",             ONOFF,                 ONOFF_REV)
_reg("le-audio",         89, 90, "mode",             ONOFF,                 ONOFF_REV)
_reg("noise-reduction",  52, 53, "mode",             NOISE_REDUCTION_MODES, NOISE_REDUCTION_MODES_REV)
_reg("buffer",           58, 59, "mode",             BUFFER_MODES,          BUFFER_MODES_REV)
_reg("switch-playing",   85, 86, "mode",             ONOFF,                 ONOFF_REV)
_reg("ringtone-talking", 87, 88, "mode",             ONOFF,                 ONOFF_REV)
_reg("assistant",         8,  9, "mode",             ASSISTANT_MODES,       ASSISTANT_MODES_REV)
# Language uses cmd 37 (getLangRev) for GET, cmd 5 for SET
_reg("safe-volume",      92, 93, "value",            None,                  None)
_reg("jmv",              46, 45, "mode",             JMV_MODES,             JMV_MODES_REV)
_reg("a2dp",             16, 17, "codec",            A2DP_CODECS,           A2DP_CODECS_REV)

# ---------------------------------------------------------------------------
#  RACE layer
# ---------------------------------------------------------------------------

def build_race_packet(cmd_id: int, payload: bytes = b"") -> bytes:
    """Build a RACE packet (head=0x05, type=0x5A, little-endian)."""
    length = 2 + len(payload)
    header = struct.pack("<BBHH", 0x05, 0x5A, length, cmd_id)
    return header + payload


def parse_race_response(data: bytes) -> tuple[int, int, bytes]:
    """Parse a RACE response. Returns (cmd_id, status, payload).

    Accepts responses (0x5B) and indications (0x5D), both
    containing valid data from the device.
    """
    if len(data) < 6:
        raise ValueError(f"Response too short: {len(data)} bytes")
    head, ptype, length, cmd_id = struct.unpack("<BBHH", data[:6])
    if ptype not in (0x5B, 0x5D):
        raise ValueError(f"Unexpected response type: 0x{ptype:02X}")
    payload = data[6:]
    status = payload[0] if payload else -1
    rest = payload[1:] if len(payload) > 1 else b""
    return cmd_id, status, rest


def bt_connect(address: str, channel: int = RFCOMM_CHANNEL) -> socket.socket:
    """Open an RFCOMM connection to the earbuds."""
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    sock.settimeout(5)
    sock.connect((address, channel))
    return sock


def send_recv(sock: socket.socket, data: bytes, timeout: float = 3,
              expected_cmd: int | None = None,
              expected_type: int | None = None) -> bytes:
    """Send data and wait for the response.

    Parses the RACE header to determine expected size and returns
    as soon as the complete packet is received (response 0x5B or indication 0x5D).
    If expected_cmd is specified, ignores packets with non-matching cmd_id.
    If expected_type is specified (0x5B or 0x5D), ignores packets of another type.
    """
    sock.send(data)
    sock.settimeout(timeout)
    buf = bytearray()
    start = time.time()
    while time.time() - start < timeout:
        try:
            chunk = sock.recv(1024)
            if not chunk:
                break
            buf.extend(chunk)
        except socket.timeout:
            if buf:
                break
            continue
        while len(buf) >= 4:
            pkt_len = 4 + struct.unpack("<H", buf[2:4])[0]
            if len(buf) < pkt_len:
                sock.settimeout(0.2)
                break
            pkt = bytes(buf[:pkt_len])
            del buf[:pkt_len]
            if pkt[1] in (0x5B, 0x5D):
                if expected_type is not None and pkt[1] != expected_type:
                    continue  # ignore wrong type packets
                if expected_cmd is not None and len(pkt) >= 6:
                    resp_cmd = struct.unpack("<H", pkt[4:6])[0]
                    if resp_cmd != expected_cmd:
                        continue  # ignore unsolicited packets
                return pkt
    if not buf:
        raise TimeoutError("No response from earbuds")
    return bytes(buf)

# ---------------------------------------------------------------------------
#  Generic helpers
# ---------------------------------------------------------------------------

def race_get(sock: socket.socket, cmd_id: int) -> bytes:
    """Generic GET, returns the payload (without the status byte)."""
    pkt = build_race_packet(cmd_id)
    resp = send_recv(sock, pkt, expected_cmd=cmd_id)
    _, status, rest = parse_race_response(resp)
    if status != 0:
        raise RuntimeError(f"GET cmd {cmd_id}: status={status}")
    return rest


def race_set(sock: socket.socket, cmd_id: int, payload: bytes) -> int:
    """Generic SET, returns the status."""
    pkt = build_race_packet(cmd_id, payload)
    resp = send_recv(sock, pkt, expected_cmd=cmd_id)
    _, status, _ = parse_race_response(resp)
    return status


def check_status(status: int, context: str = ""):
    if status != 0:
        raise RuntimeError(f"Failed{' ' + context if context else ''}: status={status}")

# ---------------------------------------------------------------------------
#  Generic GET/SET commands
# ---------------------------------------------------------------------------

def generic_get(sock: socket.socket, cmd: CmdDef) -> dict:
    """GET for a command from the generic registry."""
    data = race_get(sock, cmd.get_id)
    raw = data[0] if data else 0
    if cmd.values_rev:
        label = cmd.values_rev.get(raw, f"unknown({raw})")
    else:
        label = str(raw)
    return {cmd.field: raw, "label": label}


def generic_set(sock: socket.socket, cmd: CmdDef, value) -> dict:
    """SET for a command from the generic registry."""
    if cmd.values and isinstance(value, str):
        if value not in cmd.values:
            raise ValueError(f"Invalid value '{value}'. Choices: {list(cmd.values.keys())}")
        raw = cmd.values[value]
    else:
        raw = int(value)
    status = race_set(sock, cmd.set_id, bytes([raw]))
    check_status(status, cmd.name)
    return generic_get(sock, cmd)

# ---------------------------------------------------------------------------
#  Specialized commands
# ---------------------------------------------------------------------------

# --- EQ / Sound Mode (Airoha PEQ, cmd 0x0901/0x0900) ---

AIROHA_PEQ_GET = 0x0901
AIROHA_PEQ_SET = 0x0900


def cmd_eq_get(sock: socket.socket) -> dict:
    """GET EQ via Airoha PEQ command (Race ID 0x0901)."""
    module_id = struct.pack("<H", 0x0000)
    pkt = build_race_packet(AIROHA_PEQ_GET, module_id)
    resp = send_recv(sock, pkt, expected_cmd=AIROHA_PEQ_GET)
    _, status, rest = parse_race_response(resp)
    if status != 0:
        raise RuntimeError(f"EQ GET: status={status}")
    # rest = [module_id_lo, module_id_hi, eq_idx]
    eq_idx = rest[2] if len(rest) >= 3 else 0
    return {"sound_mode": EQ_MODES_REV.get(eq_idx, f"unknown({eq_idx})")}


def cmd_eq_set(sock: socket.socket, mode_name: str) -> dict:
    """SET EQ via Airoha PEQ command (Race ID 0x0900)."""
    if mode_name not in EQ_MODES:
        raise ValueError(f"Invalid EQ mode '{mode_name}'. Choices: {list(EQ_MODES.keys())}")
    eq_idx = EQ_MODES[mode_name]
    payload = struct.pack("<H", 0x0000) + bytes([eq_idx])
    pkt = build_race_packet(AIROHA_PEQ_SET, payload)
    resp = send_recv(sock, pkt, expected_cmd=AIROHA_PEQ_SET)
    _, status, _ = parse_race_response(resp)
    check_status(status, "EQ SET")
    return cmd_eq_get(sock)


# --- Language (cmd 37 GET / cmd 5 SET) ---

def cmd_lang_get(sock: socket.socket) -> dict:
    """GET language via cmd 37 (getLangRev).

    The response arrives as an indication (0x5D) after an ACK (0x5B).
    Contains the language byte and voice guidance firmware version.
    """
    pkt = build_race_packet(37, bytes([0]))  # 0 = LEFT
    resp = send_recv(sock, pkt, expected_cmd=37, expected_type=0x5D)
    _, status, rest = parse_race_response(resp)
    if status != 0:
        raise RuntimeError(f"Lang GET: status={status}")
    # rest = [left_right, lang_byte, str_len, version_str...]
    lang_byte = rest[1] if len(rest) >= 2 else 0
    lang = LANGUAGE_MAP_REV.get(lang_byte, f"unknown({lang_byte})")
    result = {"lang": lang_byte, "label": lang}
    if len(rest) >= 3:
        str_len = rest[2]
        if len(rest) >= 3 + str_len:
            result["version"] = rest[3:3 + str_len].rstrip(b'\x00').decode("ascii", errors="replace")
    return result


def cmd_lang_set(sock: socket.socket, lang_name: str) -> dict:
    """SET language via cmd 5."""
    if lang_name not in LANGUAGE_MAP:
        raise ValueError(f"Invalid language '{lang_name}'. Choices: {list(LANGUAGE_MAP.keys())}")
    raw = LANGUAGE_MAP[lang_name]
    status = race_set(sock, 5, bytes([raw]))
    check_status(status, "lang set")
    return cmd_lang_get(sock)


# --- ANC (cmd 10/11) ---

def cmd_anc_get(sock: socket.socket) -> dict:
    data = race_get(sock, 10)
    mode = data[0] if len(data) > 0 else 0
    nc_level = data[1] if len(data) > 1 else 0
    amb_level = data[2] if len(data) > 2 else 0
    return {
        "mode": mode,
        "mode_label": ANC_MODES_REV.get(mode, f"unknown({mode})"),
        "nc_level": nc_level,
        "ambient_level": amb_level,
    }


def cmd_anc_set(sock: socket.socket, mode_name: str) -> dict:
    if mode_name not in ANC_MODES:
        raise ValueError(f"Invalid ANC mode '{mode_name}'. Choices: {list(ANC_MODES.keys())}")
    current = cmd_anc_get(sock)
    mode = ANC_MODES[mode_name]
    payload = bytes([mode, current["nc_level"], current["ambient_level"]])
    status = race_set(sock, 11, payload)
    check_status(status, "anc set")
    return cmd_anc_get(sock)


# --- ANC Level (cmd 56/57) ---

def cmd_anc_level_get(sock: socket.socket) -> dict:
    data = race_get(sock, 56)
    raw = data[0] if data else 0
    db = NC_ADJUST_DB.get(raw)
    label = f"{db:+.1f} dB" if db is not None else "default"
    return {"level": raw, "label": label}


def cmd_anc_level_set(sock: socket.socket, level: int) -> dict:
    if level not in NC_ADJUST_DB:
        raise ValueError(f"Invalid level {level}. Values: 0 (default) or 20-40")
    status = race_set(sock, 57, bytes([level]))
    check_status(status, "anc-level set")
    return cmd_anc_level_get(sock)


# --- Spatial Audio (cmd 99/100) ---

def cmd_spatial_get(sock: socket.socket) -> dict:
    data = race_get(sock, 99)
    mode = data[0] if len(data) > 0 else 0
    ht = data[1] if len(data) > 1 else 0
    return {
        "mode": ONOFF_REV.get(mode, f"unknown({mode})"),
        "head_tracking": ONOFF_REV.get(ht, f"unknown({ht})"),
    }


def cmd_spatial_set(sock: socket.socket, mode: str, head_tracking: str | None = None) -> dict:
    if mode not in ONOFF:
        raise ValueError(f"Invalid mode '{mode}'. Choices: on, off")
    current = cmd_spatial_get(sock)
    ht_val = ONOFF[head_tracking] if head_tracking else ONOFF[current["head_tracking"]]
    payload = bytes([ONOFF[mode], ht_val])
    status = race_set(sock, 100, payload)
    check_status(status, "spatial set")
    return cmd_spatial_get(sock)


# --- Wearing Detection v3 (cmd 77/78) ---

def cmd_wearing_get(sock: socket.socket) -> dict:
    data = race_get(sock, 77)
    wd = data[0] if len(data) > 0 else 0
    music = data[1] if len(data) > 1 else 0
    touch = data[2] if len(data) > 2 else 0
    replay = data[3] if len(data) > 3 else 0
    return {
        "wearing_detection": ONOFF_REV.get(wd, str(wd)),
        "music": ONOFF_REV.get(music, str(music)),
        "touch": ONOFF_REV.get(touch, str(touch)),
        "replay": ONOFF_REV.get(replay, str(replay)),
    }


def cmd_wearing_set(sock: socket.socket, wd: str | None = None,
                    music: str | None = None, touch: str | None = None,
                    replay: str | None = None) -> dict:
    current = cmd_wearing_get(sock)
    vals = [
        ONOFF[wd] if wd else ONOFF[current["wearing_detection"]],
        ONOFF[music] if music else ONOFF[current["music"]],
        ONOFF[touch] if touch else ONOFF[current["touch"]],
        ONOFF[replay] if replay else ONOFF[current["replay"]],
    ]
    status = race_set(sock, 78, bytes(vals))
    check_status(status, "wearing set")
    return cmd_wearing_get(sock)


# --- Auto Power Off (cmd 6/7) ---

POWER_OFF_MINUTES = {5, 10, 30, 60}

def cmd_auto_power_off_get(sock: socket.socket) -> dict:
    data = race_get(sock, 6)
    mode = data[0] if len(data) > 0 else 0
    minutes = data[1] if len(data) > 1 else 0
    return {"mode": ONOFF_REV.get(mode, str(mode)), "minutes": minutes}


def cmd_auto_power_off_set(sock: socket.socket, mode: str,
                           minutes: int | None = None) -> dict:
    if mode not in ONOFF:
        raise ValueError(f"Invalid mode '{mode}'. Choices: on, off")
    current = cmd_auto_power_off_get(sock)
    mins = minutes if minutes is not None else current["minutes"]
    if mode == "on" and mins not in POWER_OFF_MINUTES:
        raise ValueError(f"Invalid minutes {mins}. Choices: {sorted(POWER_OFF_MINUTES)}")
    payload = bytes([ONOFF[mode], mins])
    status = race_set(sock, 7, payload)
    check_status(status, "auto-power-off set")
    return cmd_auto_power_off_get(sock)


# --- Ambient Mode (cmd 33/34) ---

def cmd_ambient_mode_get(sock: socket.socket) -> dict:
    data = race_get(sock, 33)
    amb = data[0] if len(data) > 0 else 0
    mus = data[1] if len(data) > 1 else 0
    return {
        "ambient_mode": AMBIENT_MODES_REV.get(amb, str(amb)),
        "music_mode": MUSIC_MODES_REV.get(mus, str(mus)),
    }


def cmd_ambient_mode_set(sock: socket.socket, ambient: str,
                         music: str | None = None) -> dict:
    if ambient not in AMBIENT_MODES:
        raise ValueError(f"Invalid mode '{ambient}'. Choices: {list(AMBIENT_MODES.keys())}")
    current = cmd_ambient_mode_get(sock)
    mus_val = MUSIC_MODES[music] if music else MUSIC_MODES[current["music_mode"]]
    payload = bytes([AMBIENT_MODES[ambient], mus_val])
    status = race_set(sock, 34, payload)
    check_status(status, "ambient-mode set")
    return cmd_ambient_mode_get(sock)


# --- Outside Toggle (cmd 21/22) ---

def cmd_outside_toggle_get(sock: socket.socket) -> dict:
    data = race_get(sock, 21)
    flags = data[0] if data else 0
    active = [name for bit, name in TOGGLE_BITS_REV.items() if flags & bit]
    return {"flags": flags, "active": active}


def cmd_outside_toggle_set(sock: socket.socket, modes: list[str]) -> dict:
    flags = 0
    for m in modes:
        m = m.strip().lower()
        if m not in TOGGLE_BITS:
            raise ValueError(f"Invalid toggle mode '{m}'. Choices: {list(TOGGLE_BITS.keys())}")
        flags |= TOGGLE_BITS[m]
    status = race_set(sock, 22, bytes([flags]))
    check_status(status, "outside-toggle set")
    return cmd_outside_toggle_get(sock)


# --- Find Me (cmd 32) - SET only ---

def cmd_find_me(sock: socket.socket, blink: bool = False,
                ring: bool = False, target: str = "both") -> dict:
    targets = {"agent": 0, "partner": 1, "both": 2}
    if target not in targets:
        raise ValueError(f"Invalid target '{target}'. Choices: {list(targets.keys())}")
    payload = bytes([int(blink), int(ring), targets[target]])
    status = race_set(sock, 32, payload)
    check_status(status, "find-me")
    return {"blink": blink, "ring": ring, "target": target, "status": "ok"}


# --- Battery ---

def _get_peer_dst(sock: socket.socket) -> tuple[int, int] | None:
    """Discover the peer (partner) destination via cmd 3328 (GetAvaDst).

    Returns (Type, Id) of the peer AWS (Type=5) or None if absent.
    """
    pkt = build_race_packet(3328)
    resp = send_recv(sock, pkt, expected_cmd=3328)
    payload = resp[6:]
    for i in range(0, len(payload) - 1, 2):
        if payload[i] == 5:  # Type=5 = AWS peer
            return (payload[i], payload[i + 1])
    return None


def _parse_tws_battery(resp: bytes) -> tuple[int, int]:
    """Parse a TWS battery response (cmd 3286, indication 0x5D).

    Returns (agent_or_client, battery_percent).
    Format: [head][type][len][cmd_id_le][status][agent_or_client][battery]
    """
    _, status, rest = parse_race_response(resp)
    if status != 0:
        raise RuntimeError(f"TWS battery: status={status}")
    agent_or_client = rest[0] if rest else 0
    level = rest[1] if len(rest) >= 2 else -1
    return agent_or_client, level


def cmd_battery_get(sock: socket.socket) -> dict:
    """Retrieve all available battery info.

    - Agent: cmd 3286 with payload {0} (indication 0x5D)
    - Partner: relay cmd 3329 wrapping cmd 3286 via peer Dst
    - Cradle: cmd 64
    """
    results = {}
    # Cradle battery (cmd 64)
    try:
        data = race_get(sock, 64)
        if data:
            results["cradle"] = data[0]
    except (TimeoutError, RuntimeError):
        pass
    # Agent battery (cmd 3286 with payload {0})
    try:
        pkt = build_race_packet(3286, bytes([0]))
        resp = send_recv(sock, pkt, expected_cmd=3286, expected_type=0x5D)
        _, level = _parse_tws_battery(resp)
        if level >= 0:
            results["agent"] = level
    except (TimeoutError, RuntimeError, ValueError):
        pass
    # Partner battery via relay (cmd 3329 wrapping cmd 3286)
    try:
        peer = _get_peer_dst(sock)
        if peer:
            inner = build_race_packet(3286, bytes([0]))
            relay_payload = bytes([peer[0], peer[1]]) + inner
            pkt = build_race_packet(3329, relay_payload)
            sock.send(pkt)
            # Collect packets until we find the relay indication
            # containing the inner indication (0x5D wrapping 0x5D)
            sock.settimeout(5)
            buf = bytearray()
            start = time.time()
            partner_level = -1
            while time.time() - start < 5:
                try:
                    chunk = sock.recv(1024)
                    if not chunk:
                        break
                    buf.extend(chunk)
                except socket.timeout:
                    if partner_level >= 0:
                        break
                    continue
                while len(buf) >= 4:
                    pkt_len = 4 + struct.unpack("<H", buf[2:4])[0]
                    if len(buf) < pkt_len:
                        sock.settimeout(0.5)
                        break
                    p = bytes(buf[:pkt_len])
                    del buf[:pkt_len]
                    # Look for relay indication (0x5D for cmd 3329)
                    # containing an inner indication (0x5D for cmd 3286)
                    if p[1] == 0x5D and len(p) >= 8:
                        inner_data = p[8:]  # after relay header (6) + Dst (2)
                        if (len(inner_data) >= 9 and inner_data[0] == 0x05
                                and inner_data[1] == 0x5D):
                            # Inner indication for cmd 3286
                            inner_status = inner_data[6]
                            if inner_status == 0 and len(inner_data) >= 9:
                                partner_level = inner_data[8]
                                break
            if partner_level >= 0:
                results["partner"] = partner_level
    except (TimeoutError, RuntimeError, ValueError):
        pass
    return results


# --- Connected Devices (cmd 73) - GET only ---

def cmd_connected_devices_get(sock: socket.socket) -> dict:
    data = race_get(sock, 73)
    if not data:
        return {"devices": []}
    # First byte is the device count
    count = data[0]
    devices = []
    offset = 1
    for _ in range(count):
        if offset >= len(data):
            break
        # Each entry: name length + name (variable format)
        # Fallback: extract what we can
        entry_len = data[offset]
        offset += 1
        if offset + entry_len <= len(data):
            raw = data[offset:offset + entry_len]
            # Try to decode as text, otherwise hex
            try:
                devices.append(raw.decode("utf-8"))
            except UnicodeDecodeError:
                devices.append(raw.hex())
            offset += entry_len
        else:
            # Dump the rest as hex
            devices.append(data[offset:].hex())
            break
    if not devices and len(data) > 1:
        return {"raw": data.hex(), "count": count}
    return {"count": count, "devices": devices}


# --- Firmware Info (cmd system 769/7688) ---

def cmd_firmware_info_get(sock: socket.socket) -> dict:
    result = {}
    # SDK Version (769 = 0x0301) - system command without status byte
    try:
        resp = send_recv(sock, build_race_packet(769))
        payload = resp[6:]  # full payload = version string
        if payload:
            result["sdk_version"] = payload.decode("utf-8", errors="replace").rstrip("\x00")
    except Exception:
        pass

    # Build Version Info (7688 = 0x1E08) - system command with status byte
    try:
        resp = send_recv(sock, build_race_packet(7688))
        _, status, data = parse_race_response(resp)
        if status == 0 and data:
            parts = data.decode("utf-8", errors="replace").rstrip("\x00").split("\x00")
            if len(parts) >= 1:
                result["soc_name"] = parts[0]
            if len(parts) >= 2:
                result["sdk_name"] = parts[1]
            if len(parts) >= 3:
                result["build_date"] = parts[2]
    except Exception:
        pass

    return result


# --- Cradle Battery (cmd 64) - GET only ---

def cmd_cradle_battery_get(sock: socket.socket) -> dict:
    data = race_get(sock, 64)
    level = data[0] if data else -1
    return {"cradle_battery": level}


# --- Codec Info (cmd 18) - GET only ---

def cmd_codec_get(sock: socket.socket) -> dict:
    data = race_get(sock, 18)
    if len(data) < 7:
        return {"codec": "unknown", "raw": data.hex()}
    codec = CODEC_TYPES.get(data[0], f"unknown({data[0]})")
    sf = SAMPLE_FREQS.get(data[1], f"unknown({data[1]})")
    cm = CHANNEL_MODES.get(data[2], f"unknown({data[2]})")
    bitrate = int.from_bytes(data[3:6], "little")
    vbr = "VBR" if len(data) > 7 and data[7] == 1 else "CBR"
    return {
        "codec": codec, "sample_freq": sf, "channel_mode": cm,
        "bitrate": bitrate, "vbr": vbr,
    }


# --- Color (cmd 2) - GET only ---

def cmd_color_get(sock: socket.socket) -> dict:
    data = race_get(sock, 2)
    raw = data[0] if data else 0
    return {"color": COLOR_MAP.get(raw, f"unknown({raw})"), "raw": raw}


# --- JMV Start (cmd 47) ---

def cmd_jmv_start(sock: socket.socket) -> dict:
    status = race_set(sock, 47, b"")
    check_status(status, "jmv start")
    return {"status": "ok"}


# --- Power Off (cmd 66) ---

def cmd_power_off(sock: socket.socket) -> dict:
    pkt = build_race_packet(66)
    resp = send_recv(sock, pkt)
    _, status, _ = parse_race_response(resp)
    check_status(status, "power-off")
    return {"status": "ok"}


# --- VP Outside (cmd 69) - SET only ---

def cmd_vp_outside_set(sock: socket.socket, mode: str) -> dict:
    if mode not in VP_OUTSIDE_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Choices: {list(VP_OUTSIDE_MODES.keys())}")
    status = race_set(sock, 69, bytes([VP_OUTSIDE_MODES[mode]]))
    check_status(status, "vp-outside set")
    return {"vp_outside": mode}


# --- VP Connected (cmd 70) - SET only ---

def cmd_vp_connected_set(sock: socket.socket, value: int) -> dict:
    if value not in VP_CONNECTED_MODES:
        raise ValueError(f"Invalid value {value}. Choices: 0-7")
    status = race_set(sock, 70, bytes([value]))
    check_status(status, "vp-connected set")
    return {"vp_connected": VP_CONNECTED_MODES[value]}


# --- VP Volume (cmd 68) - SET only ---

def cmd_vp_volume_set(sock: socket.socket, volume: int) -> dict:
    status = race_set(sock, 68, bytes([volume]))
    check_status(status, "vp-volume set")
    return {"vp_volume": volume}


# --- Status / Get All Data (cmd 240) ---

STATUS_CMD_IDS = [
    10,   # ANC
    # EQ uses Airoha PEQ (0x0901), not the Panasonic batch cmd 12
    19,   # LED
    50,   # Multipoint
    99,   # Spatial
    103,  # Adaptive ANC
    56,   # NC Adjust
    77,   # Wearing
    6,    # Auto Power Off
    33,   # Ambient Mode
    21,   # Outside Toggle
    52,   # Noise Reduction
    58,   # Buffer
    85,   # Switch Playing
    87,   # Ringtone Talking
    89,   # LE Audio
    92,   # Safe Volume
    8,    # Assistant
    # Language uses cmd 37 (getLangRev), not the batch cmd 4
    46,   # JMV
    64,   # Cradle Battery
]


def cmd_status_batch(sock: socket.socket) -> dict:
    """Retrieve all parameters via batch command 240."""
    count = len(STATUS_CMD_IDS)
    payload = bytes([count])
    for cid in STATUS_CMD_IDS:
        payload += struct.pack("<H", cid)

    pkt = build_race_packet(240, payload)
    resp = send_recv(sock, pkt, timeout=5)
    _, status, data = parse_race_response(resp)

    if status != 0:
        raise RuntimeError(f"Batch GET: status={status}")

    result = {}
    if not data:
        return result

    resp_count = data[0]
    offset = 1
    for _ in range(resp_count):
        if offset + 3 > len(data):
            break
        cid = struct.unpack("<H", data[offset:offset + 2])[0]
        dlen = data[offset + 2]
        offset += 3
        chunk = data[offset:offset + dlen]
        offset += dlen
        # Each command in the batch includes a status byte at the start
        if chunk:
            result[cid] = chunk[1:]
        else:
            result[cid] = chunk

    return _parse_batch_result(result)


def _parse_batch_result(raw: dict[int, bytes]) -> dict:
    """Transform raw batch chunks into a readable dictionary."""
    out = {}

    # ANC (10)
    if 10 in raw and len(raw[10]) >= 3:
        d = raw[10]
        out["anc"] = {
            "mode": ANC_MODES_REV.get(d[0], str(d[0])),
            "nc_level": d[1], "ambient_level": d[2],
        }

    # EQ (12)
    if 12 in raw and raw[12]:
        v = raw[12][0]
        out["eq"] = {"sound_mode": EQ_MODES_REV.get(v, str(v))}

    # LED (19)
    if 19 in raw and raw[19]:
        out["led"] = {"mode": ONOFF_REV.get(raw[19][0], str(raw[19][0]))}

    # Multipoint (50)
    if 50 in raw and raw[50]:
        out["multipoint"] = {"mode": MULTIPOINT_MODES_REV.get(raw[50][0], str(raw[50][0]))}

    # Spatial (99)
    if 99 in raw and len(raw[99]) >= 2:
        d = raw[99]
        out["spatial"] = {
            "mode": ONOFF_REV.get(d[0], str(d[0])),
            "head_tracking": ONOFF_REV.get(d[1], str(d[1])),
        }

    # Adaptive ANC (103)
    if 103 in raw and raw[103]:
        out["adaptive_anc"] = {"mode": ONOFF_REV.get(raw[103][0], str(raw[103][0]))}

    # NC Adjust (56)
    if 56 in raw and raw[56]:
        v = raw[56][0]
        db = NC_ADJUST_DB.get(v)
        out["anc_level"] = {"level": v, "label": f"{db:+.1f} dB" if db is not None else "default"}

    # Wearing (77)
    if 77 in raw and len(raw[77]) >= 4:
        d = raw[77]
        out["wearing"] = {
            "detection": ONOFF_REV.get(d[0], str(d[0])),
            "music": ONOFF_REV.get(d[1], str(d[1])),
            "touch": ONOFF_REV.get(d[2], str(d[2])),
            "replay": ONOFF_REV.get(d[3], str(d[3])),
        }

    # Auto Power Off (6)
    if 6 in raw and len(raw[6]) >= 2:
        d = raw[6]
        out["auto_power_off"] = {"mode": ONOFF_REV.get(d[0], str(d[0])), "minutes": d[1]}

    # Ambient Mode (33)
    if 33 in raw and len(raw[33]) >= 2:
        d = raw[33]
        out["ambient_mode"] = {
            "ambient": AMBIENT_MODES_REV.get(d[0], str(d[0])),
            "music": MUSIC_MODES_REV.get(d[1], str(d[1])),
        }

    # Outside Toggle (21)
    if 21 in raw and raw[21]:
        f = raw[21][0]
        out["outside_toggle"] = {
            "flags": f,
            "active": [name for bit, name in TOGGLE_BITS_REV.items() if f & bit],
        }

    # Noise Reduction (52)
    if 52 in raw and raw[52]:
        out["noise_reduction"] = {"mode": NOISE_REDUCTION_MODES_REV.get(raw[52][0], str(raw[52][0]))}

    # Buffer (58)
    if 58 in raw and raw[58]:
        out["buffer"] = {"mode": BUFFER_MODES_REV.get(raw[58][0], str(raw[58][0]))}

    # Switch Playing (85)
    if 85 in raw and raw[85]:
        out["switch_playing"] = {"mode": ONOFF_REV.get(raw[85][0], str(raw[85][0]))}

    # Ringtone Talking (87)
    if 87 in raw and raw[87]:
        out["ringtone_talking"] = {"mode": ONOFF_REV.get(raw[87][0], str(raw[87][0]))}

    # LE Audio (89)
    if 89 in raw and raw[89]:
        out["le_audio"] = {"mode": ONOFF_REV.get(raw[89][0], str(raw[89][0]))}

    # Safe Volume (92)
    if 92 in raw and raw[92]:
        out["safe_volume"] = {"value": raw[92][0]}

    # Assistant (8)
    if 8 in raw and raw[8]:
        out["assistant"] = {"mode": ASSISTANT_MODES_REV.get(raw[8][0], str(raw[8][0]))}

    # Language: uses cmd 37 (getLangRev), not in batch

    # JMV (46)
    if 46 in raw and raw[46]:
        out["jmv"] = {"mode": JMV_MODES_REV.get(raw[46][0], str(raw[46][0]))}

    # Cradle Battery (64)
    if 64 in raw and raw[64]:
        out["cradle_battery"] = {"level": raw[64][0]}

    return out

# ---------------------------------------------------------------------------
#  Display
# ---------------------------------------------------------------------------

def print_result(data: dict, raw_json: bool = False):
    if raw_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    _print_dict(data)


def _print_dict(d: dict, indent: int = 0):
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            print(f"{prefix}{k}:")
            _print_dict(v, indent + 1)
        elif isinstance(v, list):
            print(f"{prefix}{k}: {', '.join(str(x) for x in v)}")
        else:
            print(f"{prefix}{k}: {v}")

# ---------------------------------------------------------------------------
#  CLI argparse
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="technics.py",
        description="Technics EAH-AZ100 - Full control via Bluetooth RFCOMM",
    )
    p.add_argument("-a", "--address", default=None, help="Bluetooth MAC address (auto-detect if omitted)")
    p.add_argument("-c", "--channel", type=int, default=RFCOMM_CHANNEL, help="RFCOMM channel")
    p.add_argument("--raw", action="store_true", help="JSON output for scripting")

    sub = p.add_subparsers(dest="command", help="Command to execute")

    # --- Status ---
    sub.add_parser("status", help="All parameters (batch)")

    # --- Battery ---
    sub.add_parser("battery", help="Earbuds + case battery")

    # --- Codec ---
    sub.add_parser("codec", help="Current codec info")

    # --- Color ---
    sub.add_parser("color", help="Device color")

    # --- ANC ---
    sp = sub.add_parser("anc", help="Noise Canceling")
    sp.add_argument("mode", nargs="?", choices=["nc", "off", "ambient"],
                    help="ANC mode (empty = read)")

    # --- ANC Level ---
    sp = sub.add_parser("anc-level", help="Fine NC adjustment")
    sp.add_argument("level", nargs="?", type=int,
                    help="Level (0=default, 20-40)")

    # --- Adaptive ANC ---
    sp = sub.add_parser("adaptive-anc", help="Adaptive ANC")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (empty = read)")

    # --- Ambient Mode ---
    sp = sub.add_parser("ambient-mode", help="Ambient mode")
    sp.add_argument("mode", nargs="?", choices=["transparent", "attention"],
                    help="Mode (empty = read)")
    sp.add_argument("--music", choices=["play", "stop"], help="Music control")

    # --- Outside Toggle ---
    sp = sub.add_parser("outside-toggle", help="Physical button config")
    sp.add_argument("modes", nargs="?",
                    help="Comma-separated modes: off,nc,ambient (empty = read)")

    # --- EQ ---
    sp = sub.add_parser("eq", help="Equalizer")
    sp.add_argument("mode", nargs="?",
                    choices=list(EQ_MODES.keys()),
                    help="EQ preset (empty = read)")

    # --- Spatial ---
    sp = sub.add_parser("spatial", help="Spatial audio")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (empty = read)")
    sp.add_argument("--head-tracking", choices=["on", "off"],
                    help="Head tracking")

    # --- Multipoint ---
    sp = sub.add_parser("multipoint", help="Bluetooth multipoint")
    sp.add_argument("mode", nargs="?", choices=["off", "on", "triple"],
                    help="Mode (empty = read)")

    # --- Switch Playing ---
    sp = sub.add_parser("switch-playing", help="Switch during playback")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (empty = read)")

    # --- Ringtone Talking ---
    sp = sub.add_parser("ringtone-talking", help="Ringtone during call")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (empty = read)")

    # --- Auto Power Off ---
    sp = sub.add_parser("auto-power-off", help="Auto power off")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (empty = read)")
    sp.add_argument("--minutes", type=int, choices=[5, 10, 30, 60],
                    help="Duration in minutes")

    # --- LED ---
    sp = sub.add_parser("led", help="Blinking LED")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (empty = read)")

    # --- Wearing ---
    sp = sub.add_parser("wearing", help="Wearing detection")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="Detection on/off (empty = read)")
    sp.add_argument("--music", choices=["on", "off"], help="Music control")
    sp.add_argument("--touch", choices=["on", "off"], help="Touch control")
    sp.add_argument("--replay", choices=["on", "off"], help="Playback resume")

    # --- Assistant ---
    sp = sub.add_parser("assistant", help="Voice assistant")
    sp.add_argument("mode", nargs="?", choices=["google", "alexa", "off"],
                    help="Assistant (empty = read)")

    # --- LE Audio ---
    sp = sub.add_parser("le-audio", help="LE Audio")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (empty = read)")

    # --- Noise Reduction ---
    sp = sub.add_parser("noise-reduction", help="Call noise reduction")
    sp.add_argument("mode", nargs="?", choices=["normal", "high"],
                    help="Mode (empty = read)")

    # --- Buffer ---
    sp = sub.add_parser("buffer", help="Audio/video buffer")
    sp.add_argument("mode", nargs="?", choices=["auto", "music", "video"],
                    help="Mode (empty = read)")

    # --- Safe Volume ---
    sp = sub.add_parser("safe-volume", help="Safe max volume")
    sp.add_argument("value", nargs="?", type=int,
                    help="Value (empty = read)")

    # --- Language ---
    sp = sub.add_parser("language", help="Announcement language")
    sp.add_argument("lang", nargs="?", choices=list(LANGUAGE_MAP.keys()),
                    help="Language (empty = read)")

    # --- VP Outside ---
    sp = sub.add_parser("vp-outside", help="ANC change announcement")
    sp.add_argument("mode", choices=["tone", "voice"],
                    help="Announcement type")

    # --- VP Connected ---
    sp = sub.add_parser("vp-connected", help="Connection announcement")
    sp.add_argument("value", type=int, choices=range(8),
                    help="Announcement type (0-7)")

    # --- VP Volume ---
    sp = sub.add_parser("vp-volume", help="Voice prompt volume")
    sp.add_argument("volume", type=int, help="Volume")

    # --- JMV ---
    sp = sub.add_parser("jmv", help="Just My Voice")
    sp.add_argument("mode", nargs="?", choices=["on", "off", "start"],
                    help="Mode or start (empty = read)")

    # --- Find Me ---
    sp = sub.add_parser("find-me", help="Locate earbuds")
    sp.add_argument("--blink", action="store_true", help="Enable blinking")
    sp.add_argument("--ring", action="store_true", help="Enable ringing")
    sp.add_argument("--target", choices=["agent", "partner", "both"],
                    default="both", help="Target")

    # --- A2DP (codec preference) ---
    sp = sub.add_parser("a2dp", help="Bluetooth codec preference")
    sp.add_argument("codec", nargs="?",
                    choices=list(A2DP_CODECS.keys()),
                    help="Preferred codec (empty = read)")

    # --- TWS Battery (alias for battery) ---
    sub.add_parser("tws-battery", help="TWS battery (alias for battery)")

    # --- Connected Devices ---
    sub.add_parser("connected-devices", help="Connected devices")

    # --- Firmware Info ---
    sub.add_parser("firmware-info", help="Firmware info (SDK + build)")

    # --- Power Off ---
    sub.add_parser("power-off", help="Power off earbuds")

    return p

# ---------------------------------------------------------------------------
#  Dispatch
# ---------------------------------------------------------------------------

def dispatch(sock: socket.socket, args: argparse.Namespace) -> dict:
    cmd = args.command

    # --- Status batch ---
    if cmd == "status":
        return cmd_status_batch(sock)

    # --- Read only ---
    if cmd == "battery":
        return cmd_battery_get(sock)
    if cmd == "tws-battery":
        return cmd_battery_get(sock)
    if cmd == "codec":
        return cmd_codec_get(sock)
    if cmd == "color":
        return cmd_color_get(sock)
    if cmd == "connected-devices":
        return cmd_connected_devices_get(sock)
    if cmd == "firmware-info":
        return cmd_firmware_info_get(sock)

    # --- ANC ---
    if cmd == "anc":
        if args.mode:
            return cmd_anc_set(sock, args.mode)
        return cmd_anc_get(sock)

    # --- ANC Level ---
    if cmd == "anc-level":
        if args.level is not None:
            return cmd_anc_level_set(sock, args.level)
        return cmd_anc_level_get(sock)

    # --- EQ (Airoha PEQ) ---
    if cmd == "eq":
        if args.mode:
            return cmd_eq_set(sock, args.mode)
        return cmd_eq_get(sock)

    # --- Language (cmd 37 GET / cmd 5 SET) ---
    if cmd == "language":
        val = getattr(args, "lang", None)
        if val:
            return cmd_lang_set(sock, val)
        return cmd_lang_get(sock)

    # --- Spatial ---
    if cmd == "spatial":
        if args.mode:
            return cmd_spatial_set(sock, args.mode, args.head_tracking)
        return cmd_spatial_get(sock)

    # --- Wearing ---
    if cmd == "wearing":
        if args.mode or args.music or args.touch or args.replay:
            return cmd_wearing_set(sock, args.mode, args.music, args.touch, args.replay)
        return cmd_wearing_get(sock)

    # --- Auto Power Off ---
    if cmd == "auto-power-off":
        if args.mode:
            return cmd_auto_power_off_set(sock, args.mode, args.minutes)
        return cmd_auto_power_off_get(sock)

    # --- Ambient Mode ---
    if cmd == "ambient-mode":
        if args.mode:
            return cmd_ambient_mode_set(sock, args.mode, args.music)
        return cmd_ambient_mode_get(sock)

    # --- Outside Toggle ---
    if cmd == "outside-toggle":
        if args.modes:
            return cmd_outside_toggle_set(sock, args.modes.split(","))
        return cmd_outside_toggle_get(sock)

    # --- Find Me ---
    if cmd == "find-me":
        return cmd_find_me(sock, args.blink, args.ring, args.target)

    # --- Power Off ---
    if cmd == "power-off":
        return cmd_power_off(sock)

    # --- VP ---
    if cmd == "vp-outside":
        return cmd_vp_outside_set(sock, args.mode)
    if cmd == "vp-connected":
        return cmd_vp_connected_set(sock, args.value)
    if cmd == "vp-volume":
        return cmd_vp_volume_set(sock, args.volume)

    # --- JMV ---
    if cmd == "jmv":
        if args.mode == "start":
            return cmd_jmv_start(sock)
        jmv_cmd = GENERIC_CMDS["jmv"]
        if args.mode:
            return generic_set(sock, jmv_cmd, args.mode)
        return generic_get(sock, jmv_cmd)

    # --- Generic commands ---
    if cmd in GENERIC_CMDS:
        gcmd = GENERIC_CMDS[cmd]
        # Look for the value in possible argparse attributes
        val = None
        for attr in ("mode", "lang", "value", "codec"):
            val = getattr(args, attr, None)
            if val is not None:
                break
        if val is not None:
            return generic_set(sock, gcmd, val)
        return generic_get(sock, gcmd)

    raise ValueError(f"Unknown command: {cmd}")

# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    address = args.address
    if not address:
        print("  Searching for Technics earbuds...", file=sys.stderr)
        address = discover_device()
        if not address:
            print("  No Technics earbuds found among paired devices.", file=sys.stderr)
            print("  Use -a MAC to specify the address manually.", file=sys.stderr)
            sys.exit(1)
        print(f"  Earbuds found: {address}", file=sys.stderr)

    print(f"  Connecting to {address} channel {args.channel}...", file=sys.stderr)
    try:
        sock = bt_connect(address, args.channel)
    except Exception as e:
        print(f"  Connection error: {e}", file=sys.stderr)
        print("  Make sure the earbuds are connected via Bluetooth.", file=sys.stderr)
        sys.exit(1)

    try:
        result = dispatch(sock, args)
        print_result(result, raw_json=args.raw)
    except Exception as e:
        if args.raw:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            print(f"  Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
