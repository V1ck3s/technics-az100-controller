# Technics EAH-AZ100 - Bluetooth RACE Protocol

Complete documentation of the Bluetooth communication protocol for Technics EAH-AZ100 earbuds, obtained through reverse engineering of the Technics Audio Connect APK v4.3.1 (`com.panasonic.technicsaudioconnect`) and experimental validation.

---

## Device Information

| Field | Value |
|-------|-------|
| Model | Technics EAH-AZ100 |
| Bluetooth MAC | `<your-device-mac>` |
| Chipset | Airoha AB1585 (AB158x) |
| Firmware SDK | `IoT_SDK_for_BT_Audio_V3.10.0.AB158x` |
| Firmware Build | `2025/02/27 13:52:04 GMT +09:00 r10556` |
| Panasonic VID | `0x0094` (148) |
| PID | `0x0004` |
| Model ID (enum) | 160 (`MODEL_NAME_EAH_AZ100`) |
| Variants | AZ100=160, AZ100E=161, AZ100G=162, AZ100P=163 |

---

## Bluetooth Transport

### RFCOMM (Bluetooth Classic) - Used for control

| Parameter | Value |
|-----------|-------|
| RFCOMM Channel | **21** (RACE control) |
| RFCOMM Channel 2 | 2 (unidentified, does not respond to RACE commands) |
| Airoha RACE UUID | `00000000-0000-0000-0099-AABBCCDDEEFF` |
| Protocol | RACE (Remote Access Control Engine) |

### BLE GATT (unavailable when connected via Classic on Windows)

| Parameter | UUID |
|-----------|------|
| RACE Service | `5052494D-2DAB-0341-6972-6F6861424C45` |
| TX Characteristic (Host→Device) | `43484152-2DAB-3241-6972-6F6861424C45` |
| RX Characteristic (Device→Host) | `43484152-2DAB-3141-6972-6F6861424C45` |

### Exposed Bluetooth Profiles

| UUID | Service |
|------|---------|
| `0000110C` | A/V Remote Control (AVRCP) |
| `0000110E` | A/V Remote Control Target |

### Python Connection (Windows)

```python
import socket

sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
sock.settimeout(5)
sock.connect(("<your-device-mac>", 21))
```

No external dependencies required, Python stdlib >= 3.9 on Windows supports `AF_BLUETOOTH`.

---

## RACE Protocol - Packet Format

### Header Structure (6 bytes, little-endian)

```
Offset  Size    Field       Description
------  ----    -----       -----------
0x00    1       head        0x05 (normal) or 0x15 (FOTA/firmware)
0x01    1       type        Message type (see table below)
0x02    2       length      Payload size + 2 (includes cmd_id), little-endian
0x04    2       cmd_id      Command identifier, little-endian
0x06    N       payload     Variable data
```

Python struct format: `struct.pack("<BBHH", head, type, length, cmd_id) + payload`

### Message Types

| Value | Constant | Description |
|-------|----------|-------------|
| `0x5A` (90) | CMD_EXPECTS_RESPONSE | Command expecting a response |
| `0x5B` (91) | RESPONSE | Device response |
| `0x5C` (92) | CMD_EXPECTS_NO_RESPONSE | Command with no response expected |
| `0x5D` (93) | INDICATION | Spontaneous device notification |

### Building a Packet

```python
import struct

def build_race_packet(cmd_id: int, payload: bytes = b"") -> bytes:
    length = 2 + len(payload)
    header = struct.pack("<BBHH", 0x05, 0x5A, length, cmd_id)
    return header + payload
```

### Parsing a Response

```python
def parse_race_response(data: bytes) -> tuple[int, int, bytes]:
    """Returns (cmd_id, status, payload_rest)."""
    head, ptype, length, cmd_id = struct.unpack("<BBHH", data[:6])
    assert ptype == 0x5B  # RESPONSE
    payload = data[6:]
    status = payload[0] if payload else -1
    rest = payload[1:] if len(payload) > 1 else b""
    return cmd_id, status, rest
```

### Response Status Codes

| Value | Meaning |
|-------|---------|
| 0 | Success |
| 1 | Failure |
| 6 | Feature not available |
| 255 | Error |

---

## Panasonic Commands (RaceIdPana)

These commands are Panasonic/Technics specific. The cmd_id is the value shown directly.

### Complete Command Overview

| cmd_id | GET | SET | Function | SET Payload | GET Response Payload |
|--------|-----|-----|----------|-------------|----------------------|
| 0 | x | | Model ID | | status, model_id |
| 1 | | x | Model ID | model_id | status |
| 2 | x | | Color | | status, color |
| 3 | | x | Color | color | status |
| 4 | x | | Language | | status, lang |
| 5 | | x | Language | lang | status |
| 6 | x | | Auto Power Off | | status, mode, minutes |
| 7 | | x | Auto Power Off | mode, minutes | status |
| 8 | x | | Voice Assistant | | status, assistant |
| 9 | | x | Voice Assistant | assistant | status |
| **10** | **x** | | **Outside Control (ANC)** | | **status, mode, ncLevel, ambLevel** |
| **11** | | **x** | **Outside Control (ANC)** | **mode, ncLevel, ambLevel** | **status** |
| 12 | x | | Sound Mode (EQ) | | status, sound_mode |
| 13 | | x | Sound Mode (EQ) | sound_mode | status |
| 16 | x | | A2DP Option (codec) | | status, codec |
| 17 | | x | A2DP Option (codec) | codec | status |
| 18 | x | | Codec Info | | status, codec, sf, cm, bitrate[3], vbr |
| 19 | x | | LED Flash | | status, led_mode |
| 20 | | x | LED Flash | led_mode | status |
| 21 | x | | Outside Toggle config | | status, toggle_flags |
| 22 | | x | Outside Toggle config | toggle_flags | status |
| 23 | x | | Key Enable | | status, key_enable |
| 24 | | x | Key Enable | key_enable | status |
| 25 | x | | Keymap | | status, keymap_data... |
| 26 | | x | Keymap | keymap_data... | status |
| 27 | | x | Init Keymap (reset) | | status |
| 32 | | x | Find Me Alarm | blink, ring, target | status |
| 33 | x | | Ambient Mode | | status, ambient_mode, music_mode |
| 34 | | x | Ambient Mode | ambient_mode, music_mode | status |
| 35 | x | | Wearing Detection (v1) | | status, on_off |
| 36 | | x | Wearing Detection (v1) | on_off | status |
| 37 | x | | Language Revision | | status, lang_rev_data... |
| 38 | x | | Voice Trigger Language | | status, vt_lang |
| 39 | | x | Voice Trigger Language | vt_lang | status |
| 40 | x | | VTrigger Lang Revision | | status, vt_lang_rev... |
| 41 | | x | Erase Log | | status |
| 42 | x | | Log Output Path | | status, path |
| 43 | | x | Log Output Path | path | status |
| 44 | x | | Sensor Info | | status, sensor_data... |
| 45 | | x | Just My Voice | jmv_mode | status |
| 46 | x | | Just My Voice | | status, jmv_mode |
| 47 | | x | Start Just My Voice | | status |
| 48 | | x | Fix Outside Ctrl | | status |
| 50 | x | | Multi Point | | status, mp_mode |
| 51 | | x | Multi Point | mp_mode | status |
| 52 | x | | Noise Reduction | | status, nr_mode |
| 53 | | x | Noise Reduction | nr_mode | status |
| 54 | x | | BT Info | | status, bt_data... |
| 55 | x | | Quality Info | | status, quality_data... |
| 56 | x | | NC Adjust Level | | status, nc_adjust |
| 57 | | x | NC Adjust Level | nc_adjust | status |
| 58 | x | | Music/Video Buffer | | status, buffer_mode |
| 59 | | x | Music/Video Buffer | buffer_mode | status |
| 64 | x | | Cradle Battery | | status, battery_level |
| 65 | | x | Request Initialize | | status |
| 66 | | x | Request Power Off | | status |
| 67 | x | | VP Settings | | status, vp_data... |
| 68 | | x | VP Volume | volume | status |
| 69 | | x | VP Outside Ctrl announce | vp_mode | status |
| 70 | | x | VP Connected announce | vp_mode | status |
| 71 | | x | Request VP Play | | status |
| 72 | | x | Fix VP Settings | | status |
| 73 | x | | Connected Devices | | status, devices... |
| 74 | x | | Demo Mode | | status, demo_mode |
| 75 | | x | Demo Mode | demo_mode | status |
| 76 | x | | Usage Time | | status, time... |
| 77 | x | | Wearing Detection (v3) | | status, wd, music, touch, replay |
| 78 | | x | Wearing Detection (v3) | wd, music, touch, replay | status |
| 79 | | x | Start Wearing Test | params... | status |
| 80 | | x | Stop Wearing Test | | status |
| 81 | | x | Measure Wearing Test | | status |
| 82 | x | | During Wearing Test | | status, data... |
| 83 | x | | Charge Error | | status, error |
| 84 | | x | Clear Charge Error | | status |
| 85 | x | | Switch While Playing | | status, mode |
| 86 | | x | Switch While Playing | mode | status |
| 87 | x | | Ringtone While Talking | | status, mode |
| 88 | | x | Ringtone While Talking | mode | status |
| 89 | x | | LE Audio Setting | | status, le_audio |
| 90 | | x | LE Audio Setting | le_audio | status |
| 91 | x | | Current Status | | status, current_status |
| 92 | x | | Safe Max Volume | | status, max_vol |
| 93 | | x | Safe Max Volume | max_vol | status |
| 94 | x | | Board Info (Mesh) | | status, board_info |
| 95 | x | | Mesh Type | | status, mesh_type |
| 97 | x | | Cradle Version | | status, version_str... |
| 98 | | x | Usage Guide | guide | status |
| 99 | x | | Spatial Audio | | status, mode, head_tracking |
| 100 | | x | Spatial Audio | mode, head_tracking | status |
| 101 | | x | Dolby Device | dolby | status |
| 102 | x | | Dolby Play Count | | status, count |
| 103 | x | | Adaptive ANC | | status, adaptive |
| 104 | | x | Adaptive ANC | adaptive | status |
| 240 | x | | Get All Data (batch) | count, [cmd_id_lo, 0x00]... | status, count, [cmd_id, len, data...]... |

### RACE System Commands (non-Panasonic)

| cmd_id | Hex | Function | Notes |
|--------|-----|----------|-------|
| 769 | 0x0301 | SDK Version | Response 0x5B: sdk_version_str |
| 2304 | 0x0900 | Airoha PEQ SET | SET EQ via PEQ coefficients (see dedicated section) |
| 2305 | 0x0901 | Airoha PEQ GET | GET EQ via PEQ (see dedicated section) |
| 3074 | 0x0C02 | Battery Level | **Does not respond on AZ100** - use cmd 3286 instead |
| 3286 | 0x0CD6 | TWS Battery | Requires payload {0}, response via indication 0x5D (see dedicated section) |
| 3328 | 0x0D00 | GetAvaDst | Discovers relay destinations (TWS peers) |
| 3329 | 0x0D01 | RelayPassToDst | Relays a RACE command to the partner (see dedicated section) |
| 7688 | 0x1E08 | Build Version Info | Response 0x5B: soc_name, sdk_name, build_date |

---

## Main Command Details

### Outside Control (ANC) - cmd 10/11

**GET (cmd_id=10)** - Verified and tested

```
Send:     05 5A 02 00 0A 00
Response: 05 5B LL LL 0A 00 [status] [mode] [ncLevel] [ambLevel]
```

**SET (cmd_id=11)** - Verified and tested

```
Send:     05 5A 05 00 0B 00 [mode] [ncLevel] [ambLevel]
Response: 05 5B 03 00 0B 00 [status]
```

| Field | Type | Description |
|-------|------|-------------|
| mode | byte | 0=Off, 1=Noise Canceling, 2=Ambient |
| ncLevel | byte | Noise canceling level (0-100, keep current value) |
| ambLevel | byte | Ambient level (0-100, keep current value) |

**Important**: When changing modes, you must preserve the current ncLevel and ambLevel values (obtained via GET). Sending arbitrary values causes a failure (status=1).

### Ambient Mode - cmd 33/34

```
GET: 05 5A 02 00 21 00
SET: 05 5A 04 00 22 00 [ambient_mode] [music_mode]
```

| ambient_mode Value | Mode |
|--------------------|------|
| 0 | Transparent |
| 1 | Attention |

| music_mode Value | Mode |
|------------------|------|
| 0 | Play |
| 1 | Stop |

### Sound Mode (EQ) - cmd 12/13 (OBSOLETE on AZ100)

> **WARNING**: Panasonic commands 12/13 do NOT work correctly on AZ100.
> GET always returns 0 ("Unset") regardless of the actual value.
> Use Airoha PEQ commands (0x0901/0x0900) instead. See dedicated section below.

```
GET: 05 5A 02 00 0C 00   (always returns 0 on AZ100)
SET: 05 5A 03 00 0D 00 [sound_mode]  (has no effect on AZ100)
```

| Value | Mode |
|-------|------|
| 0 | Unset |
| 1 | Bass Enhancer |
| 2 | Clear Voice |
| 3 | Custom |
| 4 | Bass Enhancer 2 |
| 5 | Clear Voice 2 |
| 9 | Super Bass Enhancer |
| 10 | Custom 2 |
| 11 | Custom 3 |

### Multi Point - cmd 50/51

```
GET: 05 5A 02 00 32 00
SET: 05 5A 03 00 33 00 [mp_mode]
```

| Value | Mode |
|-------|------|
| 0 | Off |
| 1 | On (dual) |
| 2 | Triple |

### Auto Power Off - cmd 6/7

```
GET: 05 5A 02 00 06 00
SET: 05 5A 04 00 07 00 [mode] [minutes]
```

| mode Value | Mode |
|------------|------|
| 0 | Off |
| 1 | On |

| minutes Value |
|---------------|
| 5, 10, 30, 60 |

### Spatial Audio - cmd 99/100

```
GET: 05 5A 02 00 63 00
SET: 05 5A 04 00 64 00 [mode] [head_tracking]
```

| Field | 0 | 1 |
|-------|---|---|
| mode | Off | On |
| head_tracking | Off | On |

### Adaptive ANC - cmd 103/104

```
GET: 05 5A 02 00 67 00
SET: 05 5A 03 00 68 00 [adaptive]
```

| Value | Mode |
|-------|------|
| 0 | Off |
| 1 | On |

### Noise Canceling Adjust - cmd 56/57

Allows fine-tuning the noise canceling level.

```
GET: 05 5A 02 00 38 00
SET: 05 5A 03 00 39 00 [level]
```

| Value | Level |
|-------|-------|
| 0 | Default |
| 20 | -6.0 dB |
| 21 | -5.5 dB |
| 22 | -5.0 dB |
| ... | ... (0.5 dB steps) |
| 32 | 0 dB |
| 33 | +0.5 dB |
| ... | ... |
| 40 | +4.0 dB |

Adjustment mode (for SET):
| Value | Mode |
|-------|------|
| 0 | Temporary |
| 1 | Execute |
| 2 | Save Param |

### Noise Reduction (call) - cmd 52/53

```
GET: 05 5A 02 00 34 00
SET: 05 5A 03 00 35 00 [mode]
```

| Value | Mode |
|-------|------|
| 0 | Normal |
| 1 | High |

### Wearing Detection - cmd 77/78

```
GET: 05 5A 02 00 4D 00
SET: 05 5A 06 00 4E 00 [wd] [music] [touch] [replay]
```

| Field | 0 | 1 |
|-------|---|---|
| wd | Off | On |
| music | Play when removed | Stop when removed |
| touch | Not accepted | Accepted |
| replay | Off | On |

### LED Flash - cmd 19/20

```
GET: 05 5A 02 00 13 00
SET: 05 5A 03 00 14 00 [led_mode]
```

| Value | Mode |
|-------|------|
| 0 | Off |
| 1 | On |

### Voice Assistant - cmd 8/9

```
GET: 05 5A 02 00 08 00
SET: 05 5A 03 00 09 00 [assistant]
```

| Value | Assistant |
|-------|-----------|
| 0 | Unset |
| 1 | Google |
| 2 | Amazon Alexa |
| 255 | Disabled |

### LE Audio - cmd 89/90

```
GET: 05 5A 02 00 59 00
SET: 05 5A 03 00 5A 00 [setting]
```

| Value | Mode |
|-------|------|
| 0 | Off |
| 1 | On |

### Find Me - cmd 32

```
SET: 05 5A 05 00 20 00 [blink] [ring] [target]
```

| Field | 0 | 1 | 2 |
|-------|---|---|---|
| blink | Off | On | |
| ring | Off | On | |
| target | Agent | Partner | Both |

### Music/Video Buffer - cmd 58/59

```
GET: 05 5A 02 00 3A 00
SET: 05 5A 03 00 3B 00 [buffer]
```

| Value | Mode |
|-------|------|
| 0 | Auto |
| 1 | Music |
| 2 | Video |

### Battery (RACE system)

> **WARNING**: Command cmd 3074 (0x0C02) does not respond on AZ100.
> Use cmd 3286 with payload for earbuds and cmd 64 for the cradle.

#### Cradle Battery - cmd 64

Standard Panasonic command, works correctly.

```
GET: 05 5A 02 00 40 00
Response: 05 5B LL LL 40 00 [status] [battery_level]
```

| Field | Description |
|-------|-------------|
| status | 0=OK |
| battery_level | Percentage (0-100) |

#### Agent Battery - cmd 3286 (0x0CD6, TWS_GET_BATTERY)

Requires a `{0}` payload (AGENT=0). The response arrives as an **indication 0x5D** (not as a 0x5B response).

```
Send:   05 5A 03 00 D6 0C 00          (cmd 3286, payload=0x00)
ACK:    05 5B 05 00 D6 0C 00 00 XX    (0x5B, ignore)
Indic:  05 5D 05 00 D6 0C [status] [agent_or_client] [battery_percent]
```

| Field | Description |
|-------|-------------|
| send payload | 0=AGENT, 1=PARTNER (but PARTNER requires relay, see below) |
| status | 0=OK |
| agent_or_client | 0=AGENT, 1=CLIENT |
| battery_percent | Percentage (0-100) |

Decompiled source: `RaceCmdTwsGetBattery.java`, `MmiStageTwsGetBattery.java`

#### Partner Battery - via Relay cmd 3329 (0x0D01, RELAY_PASS_TO_DST)

The partner (2nd earbud) is not directly accessible. A relay mechanism must be used:

1. **Discover the peer** via cmd 3328 (GetAvaDst)
2. **Relay cmd 3286** to the partner via cmd 3329

##### Step 1: GetAvaDst - cmd 3328 (0x0D00)

```
Send:     05 5A 02 00 00 0D
Response: 05 5B LL LL 00 0D [status] [Dst_0_Type] [Dst_0_Id] [Dst_1_Type] [Dst_1_Id] ...
```

The response contains (Type, Id) pairs representing available destinations.
Look for **Type=5** (AWS peer = the TWS partner).

| Type | Meaning |
|------|---------|
| 5 | AWS Peer (TWS partner) |

Decompiled source: `MmiStageGetAvaDst.java`, `Dst.java`, `AvailabeDst.java`

##### Step 2: Relay cmd 3329 (0x0D01)

Wraps a complete RACE packet in a relay with a Dst prefix (2 bytes).

```
Relay construction:
  Inner packet: build_race_packet(3286, {0})  =>  05 5A 03 00 D6 0C 00
  Relay payload: [Dst_Type] [Dst_Id] + inner_packet
  Send: build_race_packet(3329, relay_payload)

Example with Dst Type=5, Id=6:
  Inner:  05 5A 03 00 D6 0C 00
  Relay:  05 5A 0B 00 01 0D 05 06 05 5A 03 00 D6 0C 00
```

The response arrives in multiple packets:
1. **Relay ACK** (0x5B, cmd 3329): relay status itself
2. **Inner ACK** (0x5D, cmd 3329): partner received the command
3. **Relay indication** (0x5D, cmd 3329): contains the partner's inner indication

```
Final packet (relay indication wrapping inner indication):
  05 5D LL LL 01 0D [status] [Dst_Type] [Dst_Id]  05 5D 05 00 D6 0C [inner_status] [agent_or_client] [battery_percent]
  |--- relay header (6) ---| |-- Dst (2) --|  |--- inner indication (9) ---|

Parsing:
  outer[8:]  = inner_data (after relay header + Dst)
  inner_data[0:2] = 05 5D (head + type of inner indication)
  inner_data[6]   = inner_status
  inner_data[8]   = battery_percent of partner
```

Decompiled source: `MmiStageTwsGetBatteryRelay.java`, `RaceCmdRelayPass.java`, `AgentPartnerEnum.java`

### Get All Data (batch) - cmd 240

Allows retrieving multiple parameters in a single request.

```
Send:     05 5A LL LL F0 00 [count] [cmd_id_1_lo] [0x00] [cmd_id_2_lo] [0x00] ...
Response: 05 5B LL LL F0 00 [status] [count] [cmd_id_1 (2B LE)] [len_1] [data_1...] [cmd_id_2 (2B LE)] [len_2] [data_2...] ...
```

Example: retrieve ANC (10) + Battery (64) + Spatial Audio (99):
```
05 5A 08 00 F0 00 03 0A 00 40 00 63 00
```

### Language - cmd 37 GET / cmd 5 SET

> **WARNING**: GET via cmd 4 returns an incorrect value on AZ100 (always 1="en").
> Use cmd 37 (getLangRev) for GET, which returns the actual language via a 0x5D indication.
> SET via cmd 5 works correctly.

```
GET (cmd 37, getLangRev):
  Send:   05 5A 03 00 25 00 00       (payload=0x00 for LEFT)
  ACK:    05 5B 03 00 25 00 00       (0x5B, ignore)
  Indic:  05 5D LL LL 25 00 [status] [left_right] [lang_byte] [str_len] [version_str...]

SET (cmd 5, unchanged):
  Send:     05 5A 03 00 05 00 [lang]
  Response: 05 5B 03 00 05 00 [status]
```

GET via cmd 37 returns:
| Offset (in rest) | Field | Description |
|-------------------|-------|-------------|
| 0 | left_right | 0=LEFT, 1=RIGHT |
| 1 | lang_byte | Language index (see table) |
| 2 | str_len | VP firmware version length |
| 3+ | version_str | ASCII VP version string |

| Value | Language |
|-------|----------|
| 0 | Japanese |
| 1 | English |
| 2 | German |
| 3 | French |
| 4 | French (Canada) |
| 5 | Spanish |
| 6 | Italian |
| 7 | Polish |
| 8 | Russian |
| 9 | Ukrainian |
| 10 | Chinese |
| 11 | Cantonese |

### Color - cmd 2/3

| Value | Color |
|-------|-------|
| 1 | Blue |
| 2 | Navy |
| 4 | Orange |
| 7 | Green |
| 8 | Gray |
| 11 | Black |
| 14 | Gold |
| 16 | Pink |
| 18 | Red |
| 19 | Silver |
| 20 | Brown |
| 22 | Violet |
| 23 | White |
| 25 | Yellow |
| 26 | Other |

---

## Outside Toggle (button-accessible mode configuration)

The toggle defines which ANC modes are accessible via the physical button.

```
GET: 05 5A 02 00 15 00
SET: 05 5A 03 00 16 00 [flags]
```

Flags are a bitmask:

| Bit | Value | Accessible Mode |
|-----|-------|-----------------|
| 0 | 1 | Off |
| 1 | 2 | Noise Canceling |
| 2 | 4 | Ambient |

Example: toggle between NC and Ambient only = `2 | 4 = 6`

---

## Codec Info (read-only) - cmd 18

```
GET: 05 5A 02 00 12 00
```

Response payload:
| Offset | Field | Values |
|--------|-------|--------|
| 0 | status | 0=OK |
| 1 | codec_type | 0=Unknown, 1=SBC, 2=AAC, 3=aptX, 4=aptX LL, 5=aptX HD, 6=LDAC |
| 2 | sample_freq | 1=8k, 8=44.1k, 9=48k, 12=96k |
| 3 | channel_mode | 1=Mono, 2=Dual, 3=Stereo |
| 4-6 | bitrate | 3 bytes |
| 7 | reserved | |
| 8 | vbr_flag | 0=CBR, 1=VBR |

---

## VP (Voice Prompt) Settings

### VP Outside Ctrl Announce - cmd 69

Configures the voice announcement when changing ANC mode.

```
SET: 05 5A 03 00 45 00 [vp_mode]
```

| Value | Mode |
|-------|------|
| 0 | Notification tone (beep) |
| 1 | Mode name (voice announcement) |

### VP Connected Announce - cmd 70

```
SET: 05 5A 03 00 46 00 [vp_mode]
```

| Value | Announcement |
|-------|--------------|
| 0 | "Connected" |
| 1 | Notification sound |
| 2 | "Smart Phone" |
| 3 | "Computer" |
| 4 | "Audio Player" |
| 5 | "Smart Phone 2" |
| 6 | "Tablet" |
| 7 | "Device" |

### VP Volume - cmd 68

```
SET: 05 5A 03 00 44 00 [volume]
```

---

## Supported Models by the App

| Enum | Value | Model |
|------|-------|-------|
| MODEL_NAME_EAH_AZ70W | 16 | EAH-AZ70W |
| MODEL_NAME_EAH_AZ60 | 80 | EAH-AZ60 |
| MODEL_NAME_EAH_AZ40 | 96 | EAH-AZ40 |
| MODEL_NAME_EAH_AZ80 | 112 | EAH-AZ80 |
| MODEL_NAME_EAH_AZ60M2 | 128 | EAH-AZ60M2 |
| MODEL_NAME_EAH_AZ40M2 | 144 | EAH-AZ40M2 |
| MODEL_NAME_EAH_AZ100 | 160 | EAH-AZ100 |
| MODEL_NAME_EAH_A800E | 65 | EAH-A800 (over-ear) |

Each model has regional variants (+1=E, +2=G, +3=P).

---

## Just My Voice - cmd 45/46/47

```
GET:   05 5A 02 00 2E 00
SET:   05 5A 03 00 2D 00 [mode]     (0=Off, 1=On)
START: 05 5A 02 00 2F 00
```

START response: status (0=OK, 1=NG)

---

## Switch While Playing - cmd 85/86

Controls whether multipoint can switch during audio playback.

```
GET: 05 5A 02 00 55 00
SET: 05 5A 03 00 56 00 [mode]
```

| Value | Mode |
|-------|------|
| 0 | Off |
| 1 | On |

---

## Ringtone While Talking - cmd 87/88

```
GET: 05 5A 02 00 57 00
SET: 05 5A 03 00 58 00 [mode]
```

| Value | Mode |
|-------|------|
| 0 | Off |
| 1 | On |

---

## Safe Max Volume - cmd 92/93

```
GET: 05 5A 02 00 5C 00
SET: 05 5A 03 00 5D 00 [max_vol]
```

---

## Utility Commands

### Request Power Off - cmd 66

```
SET: 05 5A 02 00 42 00
```

### Request Initialize (factory reset) - cmd 65

```
SET: 05 5A 02 00 41 00
```

### Erase Log - cmd 41

```
SET: 05 5A 02 00 29 00
```

---

## Implementation in technics.py

### Usage

```bash
uv run technics.py [-a MAC] [-c CHANNEL] [--raw] <command> [args]
```

Without arguments after the command = GET (read). With arguments = SET (write).
`--raw` produces JSON output for scripting.

### Available Commands

| CLI Command | cmd_id | Description | GET | SET |
|-------------|--------|-------------|-----|-----|
| `status` | 240 | All parameters (batch) | x | |
| `battery` | 3286+3329+64 | Battery (agent/partner/cradle) | x | |
| `codec` | 18 | Current codec info | x | |
| `color` | 2 | Device color | x | |
| `anc [nc\|off\|ambient]` | 10/11 | Noise Canceling | x | x |
| `anc-level [0-40]` | 56/57 | Fine NC adjustment (dB) | x | x |
| `adaptive-anc [on\|off]` | 103/104 | Adaptive ANC | x | x |
| `ambient-mode [transparent\|attention]` | 33/34 | Ambient mode (+ `--music`) | x | x |
| `outside-toggle [off,nc,ambient]` | 21/22 | Physical button config (bitmask) | x | x |
| `eq [off\|bass\|clear-voice\|...]` | 0x0901/0x0900 | Equalizer (Airoha PEQ) | x | x |
| `spatial [on\|off]` | 99/100 | Spatial audio (+ `--head-tracking`) | x | x |
| `multipoint [off\|on\|triple]` | 50/51 | Bluetooth multipoint | x | x |
| `switch-playing [on\|off]` | 85/86 | Switch during playback | x | x |
| `ringtone-talking [on\|off]` | 87/88 | Ringtone during call | x | x |
| `auto-power-off [on\|off]` | 6/7 | Auto power off (+ `--minutes`) | x | x |
| `led [on\|off]` | 19/20 | Flashing LED | x | x |
| `wearing [on\|off]` | 77/78 | Wearing detection (+ `--music/--touch/--replay`) | x | x |
| `assistant [google\|alexa\|off]` | 8/9 | Voice assistant | x | x |
| `le-audio [on\|off]` | 89/90 | LE Audio | x | x |
| `noise-reduction [normal\|high]` | 52/53 | Call noise reduction | x | x |
| `buffer [auto\|music\|video]` | 58/59 | Audio/video buffer | x | x |
| `safe-volume [value]` | 92/93 | Safe max volume | x | x |
| `language [ja\|en\|de\|fr\|...]` | 37/5 | Announcement language (GET via getLangRev) | x | x |
| `jmv [on\|off\|start]` | 45/46/47 | Just My Voice | x | x |
| `vp-outside [tone\|voice]` | 69 | ANC change announcement | | x |
| `vp-connected [0-7]` | 70 | Connection announcement | | x |
| `vp-volume [volume]` | 68 | Voice prompt volume | | x |
| `a2dp [sbc\|aac\|aptx\|ldac\|...]` | 16/17 | Bluetooth codec preference | x | x |
| `tws-battery` | 3286+3329 | TWS battery (alias for battery) | x | |
| `connected-devices` | 73 | Connected devices | x | |
| `firmware-info` | 769/7688 | Firmware info (SDK + build) | x | |
| `find-me` | 32 | Locate (`--blink/--ring/--target`) | | x |
| `power-off` | 66 | Turn off earbuds | | x |

### Architecture

- **Generic register**: 14 simple commands (1-byte GET/SET) via `CmdDef` + `generic_get/set`
- **Specialized functions**: 21 complex commands (multi-field, bitmask, system cmd)
- **Batch**: `status` uses command 240 to retrieve ~20 parameters in one request
- **CLI**: argparse with 34 subcommands
- **GUI**: customtkinter graphical interface (see dedicated section)

### Graphical Interface (technics_gui.py)

```bash
uv run technics_gui.py
```

customtkinter graphical interface (dark theme, 900x650) exposing all features from `technics.py`. PEP 723 dependency: `customtkinter>=5.2`.

**Architecture**:

```
App (CTk): header, sidebar (8 buttons), content, status bar
  |-- BTWorker: daemon thread + threading.Lock for RFCOMM ops
  |-- 8 pages (CTkScrollableFrame):
  |     Battery, ANC, Audio, Connection, Settings, Voice, Info, Tools
  |-- Reusable widgets: Section, ToggleRow
```

**Threading model**: All Bluetooth operations run in a daemon thread via `BTWorker`. UI callbacks use `app.after(0, callback)` for tkinter thread-safety. A `threading.Lock` serializes RFCOMM socket access. Each page uses a `_loading` flag during refresh to prevent widget callbacks from triggering BT commands.

**Pages**:

| Page | Features | Commands Used |
|------|----------|---------------|
| Battery | 3 bars (agent/partner/cradle), dynamic color | `cmd_battery_get` (agent via 3286, partner via relay 3329, cradle via 64) |
| ANC | Mode, NC level (slider), adaptive, ambient, physical button | `cmd_anc_get/set`, `cmd_anc_level_get/set`, `cmd_ambient_mode_get/set`, `cmd_outside_toggle_get/set`, generic adaptive-anc |
| Audio | EQ (9 presets), spatial, head tracking, A2DP codec, buffer, current codec | `cmd_spatial_get/set`, `cmd_codec_get`, generic eq/a2dp/buffer |
| Connection | Multipoint, LE Audio, playback switching, device list | `cmd_connected_devices_get`, generic multipoint/le-audio/switch-playing |
| Settings | LED, wearing detection (4 sub-options), auto power off, safe volume, language, ringtone | `cmd_wearing_get/set`, `cmd_auto_power_off_get/set`, generic led/safe-volume/language/ringtone-talking |
| Voice | Voice assistant, noise reduction, ANC/connection announcements, prompt volume, JMV | `cmd_vp_outside_set`, `cmd_vp_connected_set`, `cmd_vp_volume_set`, `cmd_jmv_start`, generic assistant/noise-reduction/jmv |
| Info | Firmware (SDK, SoC, build), color, full JSON status | `cmd_firmware_info_get`, `cmd_color_get`, `cmd_status_batch` |
| Tools | Locate (blink/ring/target), power off with confirmation | `cmd_find_me`, `cmd_power_off` |

**User flow**:

1. Launch → window with sidebar + Battery page
2. Click "Connect" → BT thread → green indicator if OK
3. Auto-load `cmd_status_batch()` to populate all pages
4. Sidebar navigation → `page.refresh()` loads specific data
5. Setting change → BT SET thread → feedback in status bar
6. "Disconnect" → closes socket, resets indicator to red

### Unimplemented Commands (debug/internal)

These RACE protocol commands are not exposed in `technics.py` as they are related to diagnostics, manufacturing, or advanced features rarely useful:

| cmd_id | Function | Reason |
|--------|----------|--------|
| 0/1 | Model ID | Device is already known |
| 3 | Color SET | Physical color, not software-changeable |
| 23-27 | Key Enable / Keymap | Advanced button configuration |
| 35/36 | Wearing Detection v1 | Replaced by v3 (cmd 77/78) |
| 37 | Language Revision (getLangRev) | **Used for language GET** (replaces faulty cmd 4) |
| 38-40 | VTrigger Lang / Revision | Voice trigger language firmware revision |
| 41-43 | Erase/Log Output | Internal log management |
| 44 | Sensor Info | Raw sensor data |
| 48 | Fix Outside Ctrl | Internal command |
| 54/55 | BT Info / Quality Info | Bluetooth diagnostics |
| 65 | Factory Reset | Dangerous, intentionally not exposed |
| 67 | VP Settings GET | VP read-only, not very useful |
| 71/72 | VP Play / Fix VP | Internal commands |
| 74/75 | Demo Mode | Factory demo mode |
| 76 | Usage Time | Usage counter |
| 79-82 | Wearing Test | Sensor calibration test |
| 83/84 | Charge Error | Charge diagnostics |
| 91 | Current Status | Undocumented internal state |
| 94/95 | Board/Mesh Info | Board/mesh info |
| 97 | Cradle Version | Cradle firmware version |
| 98 | Usage Guide | Undocumented |
| 101/102 | Dolby | Dolby not supported on AZ100 |

---

## Airoha Commands (non-Panasonic, non-standard RACE)

### Airoha PEQ (Parametric EQ) - cmd 0x0901 GET / 0x0900 SET

On AZ100, EQ is controlled via Airoha PEQ commands and not via Panasonic commands 12/13.

#### GET - cmd 2305 (0x0901)

```
Send:     05 5A 04 00 01 09 00 00       (payload = module_id LE = 0x0000)
Response: 05 5B LL LL 01 09 [status] [module_id_lo] [module_id_hi] [eq_idx]
```

| Field | Description |
|-------|-------------|
| module_id | 0x0000 (always) |
| eq_idx | Index of the active EQ mode (same mapping as Sound Mode cmd 12) |

#### SET - cmd 2304 (0x0900)

```
Send:     05 5A 05 00 00 09 00 00 [eq_idx]  (module_id LE + eq_idx)
Response: 05 5B LL LL 00 09 [status]
```

| eq_idx | Mode |
|--------|------|
| 0 | Off (Unset) |
| 1 | Bass Enhancer |
| 2 | Clear Voice |
| 3 | Custom |
| 4 | Bass Enhancer 2 |
| 5 | Clear Voice 2 |
| 9 | Super Bass Enhancer |
| 10 | Custom 2 |
| 11 | Custom 3 |

Decompiled source: `AirohaPeqMgr.java`, `PeqStageLoadUiData.java`, `PeqStageSetPeqGrpIdx.java`

---

## Indication Mechanism (0x5D)

Some commands do not return their data in a standard response (0x5B) but via an **indication** (0x5D). The 0x5B response then serves only as an ACK.

### Affected Commands

| cmd_id | Function | 0x5B contains | 0x5D contains |
|--------|----------|---------------|---------------|
| 37 | getLangRev | ACK (status=0) | lang_byte, version string |
| 3286 | TWS Battery | ACK (status=0, partial data) | status, agent_or_client, battery_percent |

### Filtering in send_recv

The `expected_type` parameter of `send_recv()` allows filtering the expected packet type:
- `expected_type=0x5B` (default): returns the first 0x5B response
- `expected_type=0x5D`: ignores intermediate 0x5B packets, returns the first 0x5D indication

---

## Implementation Notes

1. **Byte order**: EVERYTHING is little-endian (length, cmd_id). This is the main cause of failure if ignored.

2. **Level preservation**: For SET_OUTSIDE_CTRL, always read current levels via GET first, then send them back with the new mode. Sending arbitrary values causes a failure (status=1).

3. **No handshake**: No initialization sequence required. The RFCOMM connection is sufficient, RACE commands can be sent immediately.

4. **Timeout**: Responses typically arrive in < 500ms. A 3-second timeout is more than sufficient.

5. **Channel 21**: The RFCOMM channel for RACE is 21 on this device. Channel 2 accepts connections but does not respond to RACE commands.

6. **BLE unavailable**: On Windows, when earbuds are connected via Bluetooth Classic (for audio), BLE GATT is not accessible. Use RFCOMM only.

7. **Windows execution**: Scripts must run on the Windows side (not WSL) as Bluetooth is managed by Windows. Use `uv run` for execution without venv. From WSL, files are accessible via `\\wsl.localhost\Debian\...`.

8. **Panasonic vs Airoha commands**: Some Panasonic commands (cmd 4 GET language, cmd 12/13 EQ) do not work correctly on AZ100. The Airoha equivalents (cmd 37 getLangRev, cmd 0x0901/0x0900 PEQ) must be used instead. SET often remains functional via the Panasonic command (cmd 5 for language).

9. **Indications vs Responses**: Some commands (3286, 37) return their data in 0x5D indications rather than 0x5B responses. The 0x5B serves as an ACK. Filtering by expected packet type is required.

10. **TWS Relay**: The partner (2nd earbud) is not directly accessible. Commands must be relayed via cmd 3329 (RELAY_PASS_TO_DST) with a Dst prefix obtained via cmd 3328 (GetAvaDst). The relay response encapsulates an inner RACE packet.

---

## Errata and Corrections

The Panasonic commands documented in the initial table have been experimentally validated.
Some do not work as expected on AZ100 and had to be replaced by Airoha equivalents:

| Panasonic Command | Issue on AZ100 | Solution |
|-------------------|----------------|----------|
| cmd 4 (GET language) | Always returns 1 ("en") | Use cmd 37 (getLangRev), 0x5D indication |
| cmd 12/13 (Sound Mode EQ) | GET always returns 0, SET has no effect | Use Airoha PEQ cmd 0x0901/0x0900 |
| cmd 3074 (Battery Level) | No response | Use cmd 3286 with payload + relay 3329 for partner |

---

## Sources

- Technics Audio Connect APK v4.3.1 decompiled with jadx 1.5.1
- Package `com.airoha.libbase.RaceCommand` (RACE format, packets)
- Package `com.airoha.libbase.RaceCommand.constant` (RaceId, RaceIdPana)
- Package `com.airoha.libbase.RaceCommand.packet.pana` (Panasonic commands)
- Package `com.airoha.libmmi.stage.pana` (command stages with payloads)
- Package `com.airoha.libpeq` (PEQ stages, AirohaPeqMgr)
- Package `com.airoha.libbase.relay` (Dst, RaceCmdRelayPass, RaceCmdGetAvaDst)
- Package `com.airoha.libmmi1562.stage` (MmiStageTwsGetBattery, MmiStageTwsGetBatteryRelay, MmiStageGetAvaDst)
- Package `com.airoha.libbase.constant` (AgentPartnerEnum)
- Package `com.panasonic.audioconnect.airoha.data` (DeviceMmiConstants, OutsideCtrl)
- RACE Toolkit: https://github.com/auracast-research/race-toolkit
- ERNW White Paper 74: Airoha RACE Bluetooth Headphone Vulnerabilities
