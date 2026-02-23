# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Technics EAH-AZ100 - Controle complet via Bluetooth RFCOMM (protocole RACE)

Gere ~30 commandes GET/SET : ANC, EQ, spatial audio, batterie, codec,
multipoint, LED, wearing detection, assistant vocal, etc.
"""

import argparse
import json
import socket
import struct
import sys
import time

# ---------------------------------------------------------------------------
#  Constantes
# ---------------------------------------------------------------------------

MAC_ADDRESS = "<your-device-mac>"
RFCOMM_CHANNEL = 21

# ---------------------------------------------------------------------------
#  Tables de mapping  nom <-> valeur
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
#  Registre de commandes generiques (GET/SET 1 octet)
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

_reg("eq",               12, 13, "sound_mode",      EQ_MODES,              EQ_MODES_REV)
_reg("led",              19, 20, "mode",             ONOFF,                 ONOFF_REV)
_reg("multipoint",       50, 51, "mode",             MULTIPOINT_MODES,      MULTIPOINT_MODES_REV)
_reg("adaptive-anc",    103,104, "mode",             ONOFF,                 ONOFF_REV)
_reg("le-audio",         89, 90, "mode",             ONOFF,                 ONOFF_REV)
_reg("noise-reduction",  52, 53, "mode",             NOISE_REDUCTION_MODES, NOISE_REDUCTION_MODES_REV)
_reg("buffer",           58, 59, "mode",             BUFFER_MODES,          BUFFER_MODES_REV)
_reg("switch-playing",   85, 86, "mode",             ONOFF,                 ONOFF_REV)
_reg("ringtone-talking", 87, 88, "mode",             ONOFF,                 ONOFF_REV)
_reg("assistant",         8,  9, "mode",             ASSISTANT_MODES,       ASSISTANT_MODES_REV)
_reg("language",          4,  5, "lang",             LANGUAGE_MAP,          LANGUAGE_MAP_REV)
_reg("safe-volume",      92, 93, "value",            None,                  None)
_reg("jmv",              46, 45, "mode",             JMV_MODES,             JMV_MODES_REV)
_reg("a2dp",             16, 17, "codec",            A2DP_CODECS,           A2DP_CODECS_REV)

# ---------------------------------------------------------------------------
#  Couche RACE
# ---------------------------------------------------------------------------

def build_race_packet(cmd_id: int, payload: bytes = b"") -> bytes:
    """Construit un paquet RACE (head=0x05, type=0x5A, little-endian)."""
    length = 2 + len(payload)
    header = struct.pack("<BBHH", 0x05, 0x5A, length, cmd_id)
    return header + payload


def parse_race_response(data: bytes) -> tuple[int, int, bytes]:
    """Parse une reponse RACE. Retourne (cmd_id, status, payload).

    Accepte les reponses (0x5B) et les indications (0x5D), les deux
    contenant des donnees valides du peripherique.
    """
    if len(data) < 6:
        raise ValueError(f"Reponse trop courte: {len(data)} octets")
    head, ptype, length, cmd_id = struct.unpack("<BBHH", data[:6])
    if ptype not in (0x5B, 0x5D):
        raise ValueError(f"Type de reponse inattendu: 0x{ptype:02X}")
    payload = data[6:]
    status = payload[0] if payload else -1
    rest = payload[1:] if len(payload) > 1 else b""
    return cmd_id, status, rest


def bt_connect(address: str = MAC_ADDRESS, channel: int = RFCOMM_CHANNEL) -> socket.socket:
    """Ouvre une connexion RFCOMM vers les ecouteurs."""
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    sock.settimeout(5)
    sock.connect((address, channel))
    return sock


def send_recv(sock: socket.socket, data: bytes, timeout: float = 3) -> bytes:
    """Envoie des donnees et attend la reponse.

    Parse le header RACE pour determiner la taille attendue et retourner
    des que le paquet complet est recu (reponse 0x5B ou indication 0x5D).
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
                return pkt
    if not buf:
        raise TimeoutError("Pas de reponse des ecouteurs")
    return bytes(buf)

# ---------------------------------------------------------------------------
#  Helpers generiques
# ---------------------------------------------------------------------------

def race_get(sock: socket.socket, cmd_id: int) -> bytes:
    """GET generique, retourne le payload (sans le status byte)."""
    pkt = build_race_packet(cmd_id)
    resp = send_recv(sock, pkt)
    _, status, rest = parse_race_response(resp)
    if status != 0:
        raise RuntimeError(f"GET cmd {cmd_id}: status={status}")
    return rest


def race_set(sock: socket.socket, cmd_id: int, payload: bytes) -> int:
    """SET generique, retourne le status."""
    pkt = build_race_packet(cmd_id, payload)
    resp = send_recv(sock, pkt)
    _, status, _ = parse_race_response(resp)
    return status


def check_status(status: int, context: str = ""):
    if status != 0:
        raise RuntimeError(f"Echec{' ' + context if context else ''}: status={status}")

# ---------------------------------------------------------------------------
#  Commandes generiques GET/SET
# ---------------------------------------------------------------------------

def generic_get(sock: socket.socket, cmd: CmdDef) -> dict:
    """GET pour une commande du registre generique."""
    data = race_get(sock, cmd.get_id)
    raw = data[0] if data else 0
    if cmd.values_rev:
        label = cmd.values_rev.get(raw, f"inconnu({raw})")
    else:
        label = str(raw)
    return {cmd.field: raw, "label": label}


def generic_set(sock: socket.socket, cmd: CmdDef, value) -> dict:
    """SET pour une commande du registre generique."""
    if cmd.values and isinstance(value, str):
        if value not in cmd.values:
            raise ValueError(f"Valeur invalide '{value}'. Choix: {list(cmd.values.keys())}")
        raw = cmd.values[value]
    else:
        raw = int(value)
    status = race_set(sock, cmd.set_id, bytes([raw]))
    check_status(status, cmd.name)
    return generic_get(sock, cmd)

# ---------------------------------------------------------------------------
#  Commandes specialisees
# ---------------------------------------------------------------------------

# --- ANC (cmd 10/11) ---

def cmd_anc_get(sock: socket.socket) -> dict:
    data = race_get(sock, 10)
    mode = data[0] if len(data) > 0 else 0
    nc_level = data[1] if len(data) > 1 else 0
    amb_level = data[2] if len(data) > 2 else 0
    return {
        "mode": mode,
        "mode_label": ANC_MODES_REV.get(mode, f"inconnu({mode})"),
        "nc_level": nc_level,
        "ambient_level": amb_level,
    }


def cmd_anc_set(sock: socket.socket, mode_name: str) -> dict:
    if mode_name not in ANC_MODES:
        raise ValueError(f"Mode ANC invalide '{mode_name}'. Choix: {list(ANC_MODES.keys())}")
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
        raise ValueError(f"Niveau invalide {level}. Valeurs: 0 (default) ou 20-40")
    status = race_set(sock, 57, bytes([level]))
    check_status(status, "anc-level set")
    return cmd_anc_level_get(sock)


# --- Spatial Audio (cmd 99/100) ---

def cmd_spatial_get(sock: socket.socket) -> dict:
    data = race_get(sock, 99)
    mode = data[0] if len(data) > 0 else 0
    ht = data[1] if len(data) > 1 else 0
    return {
        "mode": ONOFF_REV.get(mode, f"inconnu({mode})"),
        "head_tracking": ONOFF_REV.get(ht, f"inconnu({ht})"),
    }


def cmd_spatial_set(sock: socket.socket, mode: str, head_tracking: str | None = None) -> dict:
    if mode not in ONOFF:
        raise ValueError(f"Mode invalide '{mode}'. Choix: on, off")
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
        raise ValueError(f"Mode invalide '{mode}'. Choix: on, off")
    current = cmd_auto_power_off_get(sock)
    mins = minutes if minutes is not None else current["minutes"]
    if mode == "on" and mins not in POWER_OFF_MINUTES:
        raise ValueError(f"Minutes invalide {mins}. Choix: {sorted(POWER_OFF_MINUTES)}")
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
        raise ValueError(f"Mode invalide '{ambient}'. Choix: {list(AMBIENT_MODES.keys())}")
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
            raise ValueError(f"Mode toggle invalide '{m}'. Choix: {list(TOGGLE_BITS.keys())}")
        flags |= TOGGLE_BITS[m]
    status = race_set(sock, 22, bytes([flags]))
    check_status(status, "outside-toggle set")
    return cmd_outside_toggle_get(sock)


# --- Find Me (cmd 32) - SET only ---

def cmd_find_me(sock: socket.socket, blink: bool = False,
                ring: bool = False, target: str = "both") -> dict:
    targets = {"agent": 0, "partner": 1, "both": 2}
    if target not in targets:
        raise ValueError(f"Target invalide '{target}'. Choix: {list(targets.keys())}")
    payload = bytes([int(blink), int(ring), targets[target]])
    status = race_set(sock, 32, payload)
    check_status(status, "find-me")
    return {"blink": blink, "ring": ring, "target": target, "status": "ok"}


# --- Battery ---

def _parse_system_battery(resp: bytes) -> tuple[str, int]:
    """Parse une reponse batterie systeme (cmd 3074/3286).

    Les commandes systeme n'ont PAS de status byte dans le payload.
    parse_race_response traite le 1er octet comme status, donc:
      - 'status' = agent_or_client (0=agent, 1=partner)
      - 'rest'   = [battery_percent]
    """
    _, role_byte, rest = parse_race_response(resp)
    role = "agent" if role_byte == 0 else "partner"
    level = rest[0] if rest else -1
    return role, level


def cmd_battery_get(sock: socket.socket) -> dict:
    """Recupere toutes les infos batterie disponibles.

    Utilise cmd 64 (Cradle Battery) comme source fiable,
    puis tente les commandes systeme 3074/3286 pour les ecouteurs.
    """
    results = {}
    # Cradle battery (cmd 64) - fonctionne sur EAH-AZ100
    try:
        data = race_get(sock, 64)
        if data:
            results["cradle"] = data[0]
    except (TimeoutError, RuntimeError):
        pass
    # Earbuds battery (cmd systeme 3074) - peut ne pas repondre
    try:
        resp = send_recv(sock, build_race_packet(3074))
        role, level = _parse_system_battery(resp)
        if level >= 0:
            results[role] = level
    except (TimeoutError, ValueError):
        pass
    # TWS battery (cmd systeme 3286) - peut ne pas repondre
    try:
        resp = send_recv(sock, build_race_packet(3286))
        role, level = _parse_system_battery(resp)
        if level >= 0:
            results[f"tws_{role}"] = level
    except (TimeoutError, ValueError):
        pass
    return results


def cmd_tws_battery_get(sock: socket.socket) -> dict:
    """TWS battery (cmd systeme 3286) - utilise par la GUI separement."""
    try:
        resp = send_recv(sock, build_race_packet(3286))
        role, level = _parse_system_battery(resp)
        return {role: level}
    except (TimeoutError, ValueError):
        return {}


# --- Connected Devices (cmd 73) - GET only ---

def cmd_connected_devices_get(sock: socket.socket) -> dict:
    data = race_get(sock, 73)
    if not data:
        return {"devices": []}
    # Le premier octet est le nombre d'appareils
    count = data[0]
    devices = []
    offset = 1
    for _ in range(count):
        if offset >= len(data):
            break
        # Chaque entree : longueur du nom + nom (format variable)
        # Fallback : on extrait ce qu'on peut
        entry_len = data[offset]
        offset += 1
        if offset + entry_len <= len(data):
            raw = data[offset:offset + entry_len]
            # Tente de decoder comme texte, sinon hex
            try:
                devices.append(raw.decode("utf-8"))
            except UnicodeDecodeError:
                devices.append(raw.hex())
            offset += entry_len
        else:
            # Dump le reste en hex
            devices.append(data[offset:].hex())
            break
    if not devices and len(data) > 1:
        return {"raw": data.hex(), "count": count}
    return {"count": count, "devices": devices}


# --- Firmware Info (cmd systeme 769/7688) ---

def cmd_firmware_info_get(sock: socket.socket) -> dict:
    result = {}
    # SDK Version (769 = 0x0301) - commande systeme sans status byte
    try:
        resp = send_recv(sock, build_race_packet(769))
        payload = resp[6:]  # payload complet = version string
        if payload:
            result["sdk_version"] = payload.decode("utf-8", errors="replace").rstrip("\x00")
    except Exception:
        pass

    # Build Version Info (7688 = 0x1E08) - commande systeme avec status byte
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
        return {"codec": "inconnu", "raw": data.hex()}
    codec = CODEC_TYPES.get(data[0], f"inconnu({data[0]})")
    sf = SAMPLE_FREQS.get(data[1], f"inconnu({data[1]})")
    cm = CHANNEL_MODES.get(data[2], f"inconnu({data[2]})")
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
    return {"color": COLOR_MAP.get(raw, f"inconnu({raw})"), "raw": raw}


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
        raise ValueError(f"Mode invalide '{mode}'. Choix: {list(VP_OUTSIDE_MODES.keys())}")
    status = race_set(sock, 69, bytes([VP_OUTSIDE_MODES[mode]]))
    check_status(status, "vp-outside set")
    return {"vp_outside": mode}


# --- VP Connected (cmd 70) - SET only ---

def cmd_vp_connected_set(sock: socket.socket, value: int) -> dict:
    if value not in VP_CONNECTED_MODES:
        raise ValueError(f"Valeur invalide {value}. Choix: 0-7")
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
    12,   # EQ
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
    4,    # Language
    46,   # JMV
    64,   # Cradle Battery
]


def cmd_status_batch(sock: socket.socket) -> dict:
    """Recupere tous les parametres via la commande batch 240."""
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
        # Chaque commande dans le batch inclut un status byte en tete
        if chunk:
            result[cid] = chunk[1:]
        else:
            result[cid] = chunk

    return _parse_batch_result(result)


def _parse_batch_result(raw: dict[int, bytes]) -> dict:
    """Transforme les chunks bruts du batch en dictionnaire lisible."""
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

    # Language (4)
    if 4 in raw and raw[4]:
        out["language"] = {"lang": LANGUAGE_MAP_REV.get(raw[4][0], str(raw[4][0]))}

    # JMV (46)
    if 46 in raw and raw[46]:
        out["jmv"] = {"mode": JMV_MODES_REV.get(raw[46][0], str(raw[46][0]))}

    # Cradle Battery (64)
    if 64 in raw and raw[64]:
        out["cradle_battery"] = {"level": raw[64][0]}

    return out

# ---------------------------------------------------------------------------
#  Affichage
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
        description="Technics EAH-AZ100 - Controle complet via Bluetooth RFCOMM",
    )
    p.add_argument("-a", "--address", default=MAC_ADDRESS, help="Adresse MAC Bluetooth")
    p.add_argument("-c", "--channel", type=int, default=RFCOMM_CHANNEL, help="Canal RFCOMM")
    p.add_argument("--raw", action="store_true", help="Sortie JSON pour scripting")

    sub = p.add_subparsers(dest="command", help="Commande a executer")

    # --- Status ---
    sub.add_parser("status", help="Tous les parametres (batch)")

    # --- Battery ---
    sub.add_parser("battery", help="Batterie ecouteurs + boitier")

    # --- Codec ---
    sub.add_parser("codec", help="Info codec actuel")

    # --- Color ---
    sub.add_parser("color", help="Couleur appareil")

    # --- ANC ---
    sp = sub.add_parser("anc", help="Noise Canceling")
    sp.add_argument("mode", nargs="?", choices=["nc", "off", "ambient"],
                    help="Mode ANC (vide = lecture)")

    # --- ANC Level ---
    sp = sub.add_parser("anc-level", help="Ajustement NC fin")
    sp.add_argument("level", nargs="?", type=int,
                    help="Niveau (0=default, 20-40)")

    # --- Adaptive ANC ---
    sp = sub.add_parser("adaptive-anc", help="ANC adaptatif")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (vide = lecture)")

    # --- Ambient Mode ---
    sp = sub.add_parser("ambient-mode", help="Mode ambiant")
    sp.add_argument("mode", nargs="?", choices=["transparent", "attention"],
                    help="Mode (vide = lecture)")
    sp.add_argument("--music", choices=["play", "stop"], help="Controle musique")

    # --- Outside Toggle ---
    sp = sub.add_parser("outside-toggle", help="Config bouton physique")
    sp.add_argument("modes", nargs="?",
                    help="Modes separes par des virgules: off,nc,ambient (vide = lecture)")

    # --- EQ ---
    sp = sub.add_parser("eq", help="Egaliseur")
    sp.add_argument("mode", nargs="?",
                    choices=list(EQ_MODES.keys()),
                    help="Preset EQ (vide = lecture)")

    # --- Spatial ---
    sp = sub.add_parser("spatial", help="Audio spatial")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (vide = lecture)")
    sp.add_argument("--head-tracking", choices=["on", "off"],
                    help="Suivi de tete")

    # --- Multipoint ---
    sp = sub.add_parser("multipoint", help="Multipoint Bluetooth")
    sp.add_argument("mode", nargs="?", choices=["off", "on", "triple"],
                    help="Mode (vide = lecture)")

    # --- Switch Playing ---
    sp = sub.add_parser("switch-playing", help="Bascule pendant la lecture")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (vide = lecture)")

    # --- Ringtone Talking ---
    sp = sub.add_parser("ringtone-talking", help="Sonnerie pendant appel")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (vide = lecture)")

    # --- Auto Power Off ---
    sp = sub.add_parser("auto-power-off", help="Arret automatique")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (vide = lecture)")
    sp.add_argument("--minutes", type=int, choices=[5, 10, 30, 60],
                    help="Duree en minutes")

    # --- LED ---
    sp = sub.add_parser("led", help="LED clignotante")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (vide = lecture)")

    # --- Wearing ---
    sp = sub.add_parser("wearing", help="Detection de port")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="Detection on/off (vide = lecture)")
    sp.add_argument("--music", choices=["on", "off"], help="Controle musique")
    sp.add_argument("--touch", choices=["on", "off"], help="Controle tactile")
    sp.add_argument("--replay", choices=["on", "off"], help="Reprise lecture")

    # --- Assistant ---
    sp = sub.add_parser("assistant", help="Assistant vocal")
    sp.add_argument("mode", nargs="?", choices=["google", "alexa", "off"],
                    help="Assistant (vide = lecture)")

    # --- LE Audio ---
    sp = sub.add_parser("le-audio", help="LE Audio")
    sp.add_argument("mode", nargs="?", choices=["on", "off"],
                    help="on/off (vide = lecture)")

    # --- Noise Reduction ---
    sp = sub.add_parser("noise-reduction", help="Reduction bruit appel")
    sp.add_argument("mode", nargs="?", choices=["normal", "high"],
                    help="Mode (vide = lecture)")

    # --- Buffer ---
    sp = sub.add_parser("buffer", help="Buffer audio/video")
    sp.add_argument("mode", nargs="?", choices=["auto", "music", "video"],
                    help="Mode (vide = lecture)")

    # --- Safe Volume ---
    sp = sub.add_parser("safe-volume", help="Volume max securise")
    sp.add_argument("value", nargs="?", type=int,
                    help="Valeur (vide = lecture)")

    # --- Language ---
    sp = sub.add_parser("language", help="Langue des annonces")
    sp.add_argument("lang", nargs="?", choices=list(LANGUAGE_MAP.keys()),
                    help="Langue (vide = lecture)")

    # --- VP Outside ---
    sp = sub.add_parser("vp-outside", help="Annonce changement ANC")
    sp.add_argument("mode", choices=["tone", "voice"],
                    help="Type d'annonce")

    # --- VP Connected ---
    sp = sub.add_parser("vp-connected", help="Annonce de connexion")
    sp.add_argument("value", type=int, choices=range(8),
                    help="Type d'annonce (0-7)")

    # --- VP Volume ---
    sp = sub.add_parser("vp-volume", help="Volume des annonces vocales")
    sp.add_argument("volume", type=int, help="Volume")

    # --- JMV ---
    sp = sub.add_parser("jmv", help="Just My Voice")
    sp.add_argument("mode", nargs="?", choices=["on", "off", "start"],
                    help="Mode ou demarrage (vide = lecture)")

    # --- Find Me ---
    sp = sub.add_parser("find-me", help="Localiser les ecouteurs")
    sp.add_argument("--blink", action="store_true", help="Activer le clignotement")
    sp.add_argument("--ring", action="store_true", help="Activer la sonnerie")
    sp.add_argument("--target", choices=["agent", "partner", "both"],
                    default="both", help="Cible")

    # --- A2DP (codec preference) ---
    sp = sub.add_parser("a2dp", help="Preference codec Bluetooth")
    sp.add_argument("codec", nargs="?",
                    choices=list(A2DP_CODECS.keys()),
                    help="Codec prefere (vide = lecture)")

    # --- TWS Battery ---
    sub.add_parser("tws-battery", help="Batterie TWS (ecouteurs separes)")

    # --- Connected Devices ---
    sub.add_parser("connected-devices", help="Appareils connectes")

    # --- Firmware Info ---
    sub.add_parser("firmware-info", help="Infos firmware (SDK + build)")

    # --- Power Off ---
    sub.add_parser("power-off", help="Eteindre les ecouteurs")

    return p

# ---------------------------------------------------------------------------
#  Dispatch
# ---------------------------------------------------------------------------

def dispatch(sock: socket.socket, args: argparse.Namespace) -> dict:
    cmd = args.command

    # --- Status batch ---
    if cmd == "status":
        return cmd_status_batch(sock)

    # --- Lecture seule ---
    if cmd == "battery":
        return cmd_battery_get(sock)
    if cmd == "tws-battery":
        return cmd_tws_battery_get(sock)
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

    # --- Commandes generiques ---
    if cmd in GENERIC_CMDS:
        gcmd = GENERIC_CMDS[cmd]
        # Cherche la valeur dans les attributs argparse possibles
        val = None
        for attr in ("mode", "lang", "value", "codec"):
            val = getattr(args, attr, None)
            if val is not None:
                break
        if val is not None:
            return generic_set(sock, gcmd, val)
        return generic_get(sock, gcmd)

    raise ValueError(f"Commande inconnue: {cmd}")

# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    print(f"  Connexion a {args.address} canal {args.channel}...", file=sys.stderr)
    try:
        sock = bt_connect(args.address, args.channel)
    except Exception as e:
        print(f"  Erreur de connexion: {e}", file=sys.stderr)
        print("  Verifie que les ecouteurs sont connectes en Bluetooth.", file=sys.stderr)
        sys.exit(1)

    try:
        result = dispatch(sock, args)
        print_result(result, raw_json=args.raw)
    except Exception as e:
        if args.raw:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            print(f"  Erreur: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
