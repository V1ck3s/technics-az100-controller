# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Technics EAH-AZ100 - Controle ANC via Bluetooth RFCOMM (RACE protocol)
"""

import socket
import struct
import sys
import time

MAC_ADDRESS = "<your-device-mac>"
RFCOMM_CHANNEL = 21

# Modes Outside Control
MODE_OFF = 0
MODE_NOISE_CANCELING = 1
MODE_AMBIENT = 2  # Transparent

MODE_NAMES = {
    MODE_OFF: "Off",
    MODE_NOISE_CANCELING: "Noise Canceling",
    MODE_AMBIENT: "Ambient (Transparent)",
}

# Race IDs Panasonic
RACE_GET_OUTSIDE_CTRL = 10  # 0x000A
RACE_SET_OUTSIDE_CTRL = 11  # 0x000B


def build_race_packet(cmd_id: int, payload: bytes = b"") -> bytes:
    """Construit un paquet RACE (head=0x05, type=0x5A, little-endian)."""
    length = 2 + len(payload)
    header = struct.pack("<BBHH", 0x05, 0x5A, length, cmd_id)
    return header + payload


def parse_race_response(data: bytes) -> tuple[int, int, bytes]:
    """Parse une reponse RACE. Retourne (cmd_id, status, payload)."""
    if len(data) < 6:
        raise ValueError(f"Reponse trop courte: {len(data)} octets")
    head, ptype, length, cmd_id = struct.unpack("<BBHH", data[:6])
    if ptype != 0x5B:
        raise ValueError(f"Type de reponse inattendu: 0x{ptype:02X}")
    payload = data[6:]
    return cmd_id, payload[0] if payload else -1, payload[1:] if len(payload) > 1 else b""


def connect(address: str = MAC_ADDRESS, channel: int = RFCOMM_CHANNEL) -> socket.socket:
    """Ouvre une connexion RFCOMM vers les ecouteurs."""
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    sock.settimeout(5)
    sock.connect((address, channel))
    return sock


def send_recv(sock: socket.socket, data: bytes, timeout: float = 3) -> bytes:
    """Envoie des donnees et attend la reponse."""
    sock.send(data)
    sock.settimeout(timeout)
    response = bytearray()
    start = time.time()
    while time.time() - start < timeout:
        try:
            chunk = sock.recv(1024)
            if chunk:
                response.extend(chunk)
                time.sleep(0.1)
            else:
                break
        except socket.timeout:
            break
    if not response:
        raise TimeoutError("Pas de reponse des ecouteurs")
    return bytes(response)


def get_anc_status(sock: socket.socket) -> dict:
    """Lit le mode ANC actuel."""
    packet = build_race_packet(RACE_GET_OUTSIDE_CTRL)
    response = send_recv(sock, packet)
    cmd_id, status, payload = parse_race_response(response)

    if status != 0:
        raise RuntimeError(f"Erreur: status={status}")

    mode = payload[0] if len(payload) > 0 else 0
    noise_cancel_level = payload[1] if len(payload) > 1 else 0
    ambient_level = payload[2] if len(payload) > 2 else 0

    return {
        "mode": mode,
        "mode_name": MODE_NAMES.get(mode, f"Inconnu ({mode})"),
        "noise_cancel_level": noise_cancel_level,
        "ambient_level": ambient_level,
    }


def set_anc_mode(sock: socket.socket, mode: int, noise_cancel_level: int = 0, ambient_level: int = 10) -> bool:
    """Change le mode ANC."""
    payload = bytes([mode, noise_cancel_level, ambient_level])
    packet = build_race_packet(RACE_SET_OUTSIDE_CTRL, payload)
    response = send_recv(sock, packet)
    cmd_id, status, _ = parse_race_response(response)
    return status == 0


def print_status(status: dict):
    print(f"  Mode actuel     : {status['mode_name']}")
    print(f"  Noise Cancel Lvl: {status['noise_cancel_level']}")
    print(f"  Ambient Level   : {status['ambient_level']}")


def main():
    usage = """
Technics EAH-AZ100 - Controle ANC

Usage:
  technics_anc.py status          Affiche le mode ANC actuel
  technics_anc.py nc              Active la reduction de bruit
  technics_anc.py off             Desactive la reduction de bruit
  technics_anc.py ambient         Active le mode transparent
  technics_anc.py transparent     Active le mode transparent (alias)
"""

    if len(sys.argv) < 2:
        print(usage)
        sys.exit(1)

    command = sys.argv[1].lower()

    print(f"  Connexion a {MAC_ADDRESS} canal {RFCOMM_CHANNEL}...")
    try:
        sock = connect()
    except Exception as e:
        print(f"  Erreur de connexion: {e}")
        print("  Verifie que les ecouteurs sont connectes en Bluetooth.")
        sys.exit(1)

    try:
        if command == "status":
            status = get_anc_status(sock)
            print_status(status)

        elif command in ("nc", "off", "ambient", "transparent"):
            # Lire le statut actuel pour conserver les niveaux
            current = get_anc_status(sock)
            nc_level = current["noise_cancel_level"]
            amb_level = current["ambient_level"]

            if command == "nc":
                print("  Activation Noise Canceling...")
                target = MODE_NOISE_CANCELING
            elif command == "off":
                print("  Desactivation ANC...")
                target = MODE_OFF
            else:
                print("  Activation mode Ambient/Transparent...")
                target = MODE_AMBIENT

            ok = set_anc_mode(sock, target, nc_level, amb_level)
            if ok:
                status = get_anc_status(sock)
                print_status(status)
            else:
                print("  Echec.")

        else:
            print(f"  Commande inconnue: {command}")
            print(usage)

    except Exception as e:
        print(f"  Erreur: {e}")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
