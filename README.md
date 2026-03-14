# Technics EAH-AZ100 Controller

Unofficial Bluetooth controller for Technics EAH-AZ100 earbuds. Communicates over RFCOMM using the Airoha RACE protocol, reverse-engineered from the Technics Audio Connect APK.

## Features

Full GET/SET control over 30+ settings:

- **ANC** - Noise Canceling / Ambient / Off, NC level adjustment, adaptive ANC
- **Equalizer** - 9 presets via Airoha PEQ (Bass Enhancer, Clear Voice, Custom, etc.)
- **Spatial Audio** - On/Off with head tracking toggle
- **Battery** - Agent, partner (via TWS relay) and cradle levels
- **Bluetooth** - Multipoint (dual/triple), LE Audio, A2DP codec preference
- **Wearing Detection** - Auto-pause, touch lock, instant replay
- **Voice Prompts** - Assistant (Google/Alexa), ANC announcements, volume
- **Utilities** - Find Me (blink/ring), LED, auto power off, power off, and more

## Requirements

- **Python** >= 3.11
- **Windows** (Bluetooth stack required - does not work from WSL)
- **[uv](https://docs.astral.sh/uv/)** (recommended, handles inline dependencies automatically)

No external dependencies for the CLI. The GUI requires `customtkinter>=5.2` (auto-installed by `uv`).

## Usage

### CLI

The device MAC address is auto-detected from paired Bluetooth devices. Use `-a MAC` to specify manually.

```bash
# Read all settings at once
uv run technics.py status

# Get / set ANC
uv run technics.py anc
uv run technics.py anc nc

# Get / set EQ
uv run technics.py eq
uv run technics.py eq bass

# Battery levels
uv run technics.py battery

# Spatial audio with head tracking
uv run technics.py spatial on --head-tracking on

# JSON output for scripting
uv run technics.py --raw status
```

Run `uv run technics.py --help` for the full list of commands.

### GUI

```bash
uv run technics_gui.py
```

Dark-themed customtkinter interface (900×650) with 8 pages: Battery, ANC, Audio, Connection, Settings, Voice, Info, and Tools. All Bluetooth operations run in a background thread.

### Build standalone executable

```bash
uv run build_gui.py
# Output: dist/technics_gui.exe
```

## Protocol Documentation

See [PROTOCOL.md](PROTOCOL.md) for the complete RACE protocol reference, including packet format, command table, relay mechanism, and implementation notes.

## How It Works

Connects via Bluetooth RFCOMM (channel 21) to the Airoha AB1585 chipset and sends/receives RACE (Remote Access Control Engine) packets. No pairing handshake needed beyond standard Bluetooth - commands can be sent immediately after connecting the socket.

Some Panasonic-layer commands (EQ, language GET, battery) are broken on AZ100 and are replaced by Airoha-native equivalents (PEQ, getLangRev, TWS battery + relay).

## License

This project is provided as-is for educational and personal use. The protocol information was obtained through reverse engineering of the publicly available Technics Audio Connect APK.
