# Technics EAH-AZ100 - Protocole Bluetooth RACE

Documentation complete du protocole de communication Bluetooth des ecouteurs Technics EAH-AZ100, obtenue par reverse engineering de l'APK Technics Audio Connect v4.3.1 (`com.panasonic.technicsaudioconnect`) et validation experimentale.

---

## Informations appareil

| Champ | Valeur |
|-------|--------|
| Modele | Technics EAH-AZ100 |
| MAC Bluetooth | `<your-device-mac>` |
| Chipset | Airoha AB1585 (AB158x) |
| SDK Firmware | `IoT_SDK_for_BT_Audio_V3.10.0.AB158x` |
| Build Firmware | `2025/02/27 13:52:04 GMT +09:00 r10556` |
| VID Panasonic | `0x0094` (148) |
| PID | `0x0004` |
| Model ID (enum) | 160 (`MODEL_NAME_EAH_AZ100`) |
| Variantes | AZ100=160, AZ100E=161, AZ100G=162, AZ100P=163 |

---

## Transport Bluetooth

### RFCOMM (Bluetooth Classic) - Utilise pour le controle

| Parametre | Valeur |
|-----------|--------|
| Canal RFCOMM | **21** (controle RACE) |
| Canal RFCOMM 2 | 2 (non identifie, ne repond pas aux commandes RACE) |
| UUID RACE Airoha | `00000000-0000-0000-0099-AABBCCDDEEFF` |
| Protocole | RACE (Remote Access Control Engine) |

### BLE GATT (non disponible quand connecte en Classic sur Windows)

| Parametre | UUID |
|-----------|------|
| Service RACE | `5052494D-2DAB-0341-6972-6F6861424C45` |
| Characteristic TX (Host→Device) | `43484152-2DAB-3241-6972-6F6861424C45` |
| Characteristic RX (Device→Host) | `43484152-2DAB-3141-6972-6F6861424C45` |

### Profils Bluetooth exposes

| UUID | Service |
|------|---------|
| `0000110C` | A/V Remote Control (AVRCP) |
| `0000110E` | A/V Remote Control Target |

### Connexion Python (Windows)

```python
import socket

sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
sock.settimeout(5)
sock.connect(("<your-device-mac>", 21))
```

Aucune dependance externe requise, la stdlib Python >= 3.9 sur Windows supporte `AF_BLUETOOTH`.

---

## Protocole RACE - Format de paquet

### Structure de l'en-tete (6 octets, little-endian)

```
Offset  Taille  Champ       Description
------  ------  -----       -----------
0x00    1       head        0x05 (normal) ou 0x15 (FOTA/firmware)
0x01    1       type        Type de message (voir tableau ci-dessous)
0x02    2       length      Taille du payload + 2 (inclut cmd_id), little-endian
0x04    2       cmd_id      Identifiant de commande, little-endian
0x06    N       payload     Donnees variables
```

Format struct Python : `struct.pack("<BBHH", head, type, length, cmd_id) + payload`

### Types de messages

| Valeur | Constante | Description |
|--------|-----------|-------------|
| `0x5A` (90) | CMD_EXPECTS_RESPONSE | Commande avec reponse attendue |
| `0x5B` (91) | RESPONSE | Reponse du peripherique |
| `0x5C` (92) | CMD_EXPECTS_NO_RESPONSE | Commande sans reponse |
| `0x5D` (93) | INDICATION | Notification spontanee du peripherique |

### Construction d'un paquet

```python
import struct

def build_race_packet(cmd_id: int, payload: bytes = b"") -> bytes:
    length = 2 + len(payload)
    header = struct.pack("<BBHH", 0x05, 0x5A, length, cmd_id)
    return header + payload
```

### Parsing d'une reponse

```python
def parse_race_response(data: bytes) -> tuple[int, int, bytes]:
    """Retourne (cmd_id, status, payload_rest)."""
    head, ptype, length, cmd_id = struct.unpack("<BBHH", data[:6])
    assert ptype == 0x5B  # RESPONSE
    payload = data[6:]
    status = payload[0] if payload else -1
    rest = payload[1:] if len(payload) > 1 else b""
    return cmd_id, status, rest
```

### Codes de statut dans les reponses

| Valeur | Signification |
|--------|---------------|
| 0 | Succes |
| 1 | Echec |
| 6 | Fonction non disponible |
| 255 | Erreur |

---

## Commandes Panasonic (RaceIdPana)

Ces commandes sont specifiques a Panasonic/Technics. Le cmd_id est directement la valeur indiquee.

### Vue d'ensemble de toutes les commandes

| cmd_id | GET | SET | Fonction | Payload SET | Payload reponse GET |
|--------|-----|-----|----------|-------------|---------------------|
| 0 | x | | Model ID | | status, model_id |
| 1 | | x | Model ID | model_id | status |
| 2 | x | | Couleur | | status, color |
| 3 | | x | Couleur | color | status |
| 4 | x | | Langue | | status, lang |
| 5 | | x | Langue | lang | status |
| 6 | x | | Auto Power Off | | status, mode, minutes |
| 7 | | x | Auto Power Off | mode, minutes | status |
| 8 | x | | Assistant vocal | | status, assistant |
| 9 | | x | Assistant vocal | assistant | status |
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

### Commandes systeme RACE (non Panasonic)

| cmd_id | Hex | Fonction | Notes |
|--------|-----|----------|-------|
| 769 | 0x0301 | SDK Version | Reponse 0x5B : sdk_version_str |
| 2304 | 0x0900 | Airoha PEQ SET | SET EQ via coefficients PEQ (voir section dediee) |
| 2305 | 0x0901 | Airoha PEQ GET | GET EQ via PEQ (voir section dediee) |
| 3074 | 0x0C02 | Battery Level | **Ne repond pas sur AZ100** - utiliser cmd 3286 |
| 3286 | 0x0CD6 | TWS Battery | Requiert payload {0}, reponse en indication 0x5D (voir section dediee) |
| 3328 | 0x0D00 | GetAvaDst | Decouvre les destinations relay (peers TWS) |
| 3329 | 0x0D01 | RelayPassToDst | Relay une commande RACE vers le partner (voir section dediee) |
| 7688 | 0x1E08 | Build Version Info | Reponse 0x5B : soc_name, sdk_name, build_date |

---

## Detail des commandes principales

### Outside Control (ANC) - cmd 10/11

**GET (cmd_id=10)** - Verifie et teste

```
Envoi:  05 5A 02 00 0A 00
Reponse: 05 5B LL LL 0A 00 [status] [mode] [ncLevel] [ambLevel]
```

**SET (cmd_id=11)** - Verifie et teste

```
Envoi:  05 5A 05 00 0B 00 [mode] [ncLevel] [ambLevel]
Reponse: 05 5B 03 00 0B 00 [status]
```

| Champ | Type | Description |
|-------|------|-------------|
| mode | byte | 0=Off, 1=Noise Canceling, 2=Ambient |
| ncLevel | byte | Niveau de reduction de bruit (0-100, garder la valeur actuelle) |
| ambLevel | byte | Niveau ambiant (0-100, garder la valeur actuelle) |

**Important** : lors du changement de mode, il faut conserver les valeurs ncLevel et ambLevel actuelles (obtenues via GET). Envoyer des valeurs arbitraires cause un echec (status=1).

### Ambient Mode - cmd 33/34

```
GET: 05 5A 02 00 21 00
SET: 05 5A 04 00 22 00 [ambient_mode] [music_mode]
```

| Valeur ambient_mode | Mode |
|---------------------|------|
| 0 | Transparent |
| 1 | Attention |

| Valeur music_mode | Mode |
|-------------------|------|
| 0 | Play |
| 1 | Stop |

### Sound Mode (EQ) - cmd 12/13 (OBSOLETE sur AZ100)

> **ATTENTION** : Les commandes Panasonic 12/13 ne fonctionnent PAS correctement sur AZ100.
> Le GET retourne toujours 0 ("Unset") quelle que soit la valeur reelle.
> Utiliser les commandes Airoha PEQ (0x0901/0x0900) a la place. Voir section dediee ci-dessous.

```
GET: 05 5A 02 00 0C 00   (retourne toujours 0 sur AZ100)
SET: 05 5A 03 00 0D 00 [sound_mode]  (ne prend pas effet sur AZ100)
```

| Valeur | Mode |
|--------|------|
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

| Valeur | Mode |
|--------|------|
| 0 | Off |
| 1 | On (dual) |
| 2 | Triple |

### Auto Power Off - cmd 6/7

```
GET: 05 5A 02 00 06 00
SET: 05 5A 04 00 07 00 [mode] [minutes]
```

| Valeur mode | Mode |
|-------------|------|
| 0 | Off |
| 1 | On |

| Valeur minutes |
|----------------|
| 5, 10, 30, 60 |

### Spatial Audio - cmd 99/100

```
GET: 05 5A 02 00 63 00
SET: 05 5A 04 00 64 00 [mode] [head_tracking]
```

| Champ | 0 | 1 |
|-------|---|---|
| mode | Off | On |
| head_tracking | Off | On |

### Adaptive ANC - cmd 103/104

```
GET: 05 5A 02 00 67 00
SET: 05 5A 03 00 68 00 [adaptive]
```

| Valeur | Mode |
|--------|------|
| 0 | Off |
| 1 | On |

### Noise Canceling Adjust - cmd 56/57

Permet d'ajuster finement le niveau de reduction de bruit.

```
GET: 05 5A 02 00 38 00
SET: 05 5A 03 00 39 00 [level]
```

| Valeur | Niveau |
|--------|--------|
| 0 | Default |
| 20 | -6.0 dB |
| 21 | -5.5 dB |
| 22 | -5.0 dB |
| ... | ... (pas de 0.5 dB) |
| 32 | 0 dB |
| 33 | +0.5 dB |
| ... | ... |
| 40 | +4.0 dB |

Mode d'ajustement (pour SET) :
| Valeur | Mode |
|--------|------|
| 0 | Temporary |
| 1 | Execute |
| 2 | Save Param |

### Noise Reduction (appel) - cmd 52/53

```
GET: 05 5A 02 00 34 00
SET: 05 5A 03 00 35 00 [mode]
```

| Valeur | Mode |
|--------|------|
| 0 | Normal |
| 1 | High |

### Wearing Detection - cmd 77/78

```
GET: 05 5A 02 00 4D 00
SET: 05 5A 06 00 4E 00 [wd] [music] [touch] [replay]
```

| Champ | 0 | 1 |
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

| Valeur | Mode |
|--------|------|
| 0 | Off |
| 1 | On |

### Assistant vocal - cmd 8/9

```
GET: 05 5A 02 00 08 00
SET: 05 5A 03 00 09 00 [assistant]
```

| Valeur | Assistant |
|--------|-----------|
| 0 | Unset |
| 1 | Google |
| 2 | Amazon Alexa |
| 255 | Disabled |

### LE Audio - cmd 89/90

```
GET: 05 5A 02 00 59 00
SET: 05 5A 03 00 5A 00 [setting]
```

| Valeur | Mode |
|--------|------|
| 0 | Off |
| 1 | On |

### Find Me - cmd 32

```
SET: 05 5A 05 00 20 00 [blink] [ring] [target]
```

| Champ | 0 | 1 | 2 |
|-------|---|---|---|
| blink | Off | On | |
| ring | Off | On | |
| target | Agent | Partner | Both |

### Music/Video Buffer - cmd 58/59

```
GET: 05 5A 02 00 3A 00
SET: 05 5A 03 00 3B 00 [buffer]
```

| Valeur | Mode |
|--------|------|
| 0 | Auto |
| 1 | Music |
| 2 | Video |

### Battery (systeme RACE)

> **ATTENTION** : La commande cmd 3074 (0x0C02) ne repond pas sur AZ100.
> Utiliser cmd 3286 avec payload pour les ecouteurs et cmd 64 pour le boitier.

#### Cradle Battery - cmd 64

Commande Panasonic standard, fonctionne correctement.

```
GET: 05 5A 02 00 40 00
Reponse: 05 5B LL LL 40 00 [status] [battery_level]
```

| Champ | Description |
|-------|-------------|
| status | 0=OK |
| battery_level | Pourcentage (0-100) |

#### Agent Battery - cmd 3286 (0x0CD6, TWS_GET_BATTERY)

Necessite un payload `{0}` (AGENT=0). La reponse arrive en **indication 0x5D** (pas en reponse 0x5B).

```
Envoi:  05 5A 03 00 D6 0C 00          (cmd 3286, payload=0x00)
ACK:    05 5B 05 00 D6 0C 00 00 XX    (0x5B, ignorer)
Indic:  05 5D 05 00 D6 0C [status] [agent_or_client] [battery_percent]
```

| Champ | Description |
|-------|-------------|
| payload envoi | 0=AGENT, 1=PARTNER (mais PARTNER necessite relay, voir ci-dessous) |
| status | 0=OK |
| agent_or_client | 0=AGENT, 1=CLIENT |
| battery_percent | Pourcentage (0-100) |

Source decompilee : `RaceCmdTwsGetBattery.java`, `MmiStageTwsGetBattery.java`

#### Partner Battery - via Relay cmd 3329 (0x0D01, RELAY_PASS_TO_DST)

Le partner (2eme ecouteur) n'est pas directement accessible. Il faut passer par un mecanisme de relay :

1. **Decouvrir le peer** via cmd 3328 (GetAvaDst)
2. **Relayer cmd 3286** au partner via cmd 3329

##### Etape 1 : GetAvaDst - cmd 3328 (0x0D00)

```
Envoi:  05 5A 02 00 00 0D
Reponse: 05 5B LL LL 00 0D [status] [Dst_0_Type] [Dst_0_Id] [Dst_1_Type] [Dst_1_Id] ...
```

La reponse contient des paires (Type, Id) representant les destinations disponibles.
Chercher **Type=5** (AWS peer = le partner TWS).

| Type | Signification |
|------|---------------|
| 5 | AWS Peer (partner TWS) |

Source decompilee : `MmiStageGetAvaDst.java`, `Dst.java`, `AvailabeDst.java`

##### Etape 2 : Relay cmd 3329 (0x0D01)

Emballe un paquet RACE complet dans un relay avec un prefixe Dst (2 octets).

```
Construction du relay :
  Inner packet : build_race_packet(3286, {0})  =>  05 5A 03 00 D6 0C 00
  Relay payload : [Dst_Type] [Dst_Id] + inner_packet
  Envoi : build_race_packet(3329, relay_payload)

Exemple avec Dst Type=5, Id=6 :
  Inner:  05 5A 03 00 D6 0C 00
  Relay:  05 5A 0B 00 01 0D 05 06 05 5A 03 00 D6 0C 00
```

La reponse arrive en plusieurs paquets :
1. **ACK relay** (0x5B, cmd 3329) : status du relay lui-meme
2. **ACK inner** (0x5D, cmd 3329) : le partner a recu la commande
3. **Indication relay** (0x5D, cmd 3329) : contient l'indication interne du partner

```
Paquet final (indication relay wrappant indication interne) :
  05 5D LL LL 01 0D [status] [Dst_Type] [Dst_Id]  05 5D 05 00 D6 0C [inner_status] [agent_or_client] [battery_percent]
  |--- header relay (6) --| |-- Dst (2) --|  |--- inner indication (9) ---|

Parsing :
  outer[8:]  = inner_data (apres header relay + Dst)
  inner_data[0:2] = 05 5D (head + type de l'indication interne)
  inner_data[6]   = inner_status
  inner_data[8]   = battery_percent du partner
```

Source decompilee : `MmiStageTwsGetBatteryRelay.java`, `RaceCmdRelayPass.java`, `AgentPartnerEnum.java`

### Get All Data (batch) - cmd 240

Permet de recuperer plusieurs parametres en une seule requete.

```
Envoi:  05 5A LL LL F0 00 [count] [cmd_id_1_lo] [0x00] [cmd_id_2_lo] [0x00] ...
Reponse: 05 5B LL LL F0 00 [status] [count] [cmd_id_1 (2B LE)] [len_1] [data_1...] [cmd_id_2 (2B LE)] [len_2] [data_2...] ...
```

Exemple : recuperer ANC (10) + Battery (64) + Spatial Audio (99) :
```
05 5A 08 00 F0 00 03 0A 00 40 00 63 00
```

### Langue - cmd 37 GET / cmd 5 SET

> **ATTENTION** : Le GET via cmd 4 retourne une valeur incorrecte sur AZ100 (toujours 1="en").
> Utiliser cmd 37 (getLangRev) pour le GET, qui retourne la langue reelle via une indication 0x5D.
> Le SET via cmd 5 fonctionne correctement.

```
GET (cmd 37, getLangRev):
  Envoi:  05 5A 03 00 25 00 00       (payload=0x00 pour LEFT)
  ACK:    05 5B 03 00 25 00 00       (0x5B, ignorer)
  Indic:  05 5D LL LL 25 00 [status] [left_right] [lang_byte] [str_len] [version_str...]

SET (cmd 5, inchange):
  Envoi:  05 5A 03 00 05 00 [lang]
  Reponse: 05 5B 03 00 05 00 [status]
```

Le GET via cmd 37 retourne :
| Offset (dans rest) | Champ | Description |
|---------------------|-------|-------------|
| 0 | left_right | 0=LEFT, 1=RIGHT |
| 1 | lang_byte | Index de langue (voir tableau) |
| 2 | str_len | Longueur de la version firmware VP |
| 3+ | version_str | String ASCII de la version VP |

| Valeur | Langue |
|--------|--------|
| 0 | Japonais |
| 1 | Anglais |
| 2 | Allemand |
| 3 | Francais |
| 4 | Francais (Canada) |
| 5 | Espagnol |
| 6 | Italien |
| 7 | Polonais |
| 8 | Russe |
| 9 | Ukrainien |
| 10 | Chinois |
| 11 | Cantonais |

### Couleur - cmd 2/3

| Valeur | Couleur |
|--------|---------|
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

## Outside Toggle (configuration des modes accessibles par bouton)

Le toggle definit quels modes ANC sont accessibles via le bouton physique.

```
GET: 05 5A 02 00 15 00
SET: 05 5A 03 00 16 00 [flags]
```

Les flags sont un bitmask :

| Bit | Valeur | Mode accessible |
|-----|--------|-----------------|
| 0 | 1 | Off |
| 1 | 2 | Noise Canceling |
| 2 | 4 | Ambient |

Exemple : toggle entre NC et Ambient uniquement = `2 | 4 = 6`

---

## Codec Info (lecture seule) - cmd 18

```
GET: 05 5A 02 00 12 00
```

Reponse payload :
| Offset | Champ | Valeurs |
|--------|-------|---------|
| 0 | status | 0=OK |
| 1 | codec_type | 0=Unknown, 1=SBC, 2=AAC, 3=aptX, 4=aptX LL, 5=aptX HD, 6=LDAC |
| 2 | sample_freq | 1=8k, 8=44.1k, 9=48k, 12=96k |
| 3 | channel_mode | 1=Mono, 2=Dual, 3=Stereo |
| 4-6 | bitrate | 3 octets |
| 7 | reserved | |
| 8 | vbr_flag | 0=CBR, 1=VBR |

---

## VP (Voice Prompt) Settings

### VP Outside Ctrl Announce - cmd 69

Configure l'annonce vocale lors du changement de mode ANC.

```
SET: 05 5A 03 00 45 00 [vp_mode]
```

| Valeur | Mode |
|--------|------|
| 0 | Notification tone (bip) |
| 1 | Mode name (annonce vocale) |

### VP Connected Announce - cmd 70

```
SET: 05 5A 03 00 46 00 [vp_mode]
```

| Valeur | Annonce |
|--------|---------|
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

## Modeles supportes par l'app

| Enum | Valeur | Modele |
|------|--------|--------|
| MODEL_NAME_EAH_AZ70W | 16 | EAH-AZ70W |
| MODEL_NAME_EAH_AZ60 | 80 | EAH-AZ60 |
| MODEL_NAME_EAH_AZ40 | 96 | EAH-AZ40 |
| MODEL_NAME_EAH_AZ80 | 112 | EAH-AZ80 |
| MODEL_NAME_EAH_AZ60M2 | 128 | EAH-AZ60M2 |
| MODEL_NAME_EAH_AZ40M2 | 144 | EAH-AZ40M2 |
| MODEL_NAME_EAH_AZ100 | 160 | EAH-AZ100 |
| MODEL_NAME_EAH_A800E | 65 | EAH-A800 (over-ear) |

Chaque modele a des variantes regionales (+1=E, +2=G, +3=P).

---

## Just My Voice - cmd 45/46/47

```
GET:   05 5A 02 00 2E 00
SET:   05 5A 03 00 2D 00 [mode]     (0=Off, 1=On)
START: 05 5A 02 00 2F 00
```

Reponse START : status (0=OK, 1=NG)

---

## Switch While Playing - cmd 85/86

Controle si le multipoint peut basculer pendant la lecture audio.

```
GET: 05 5A 02 00 55 00
SET: 05 5A 03 00 56 00 [mode]
```

| Valeur | Mode |
|--------|------|
| 0 | Off |
| 1 | On |

---

## Ringtone While Talking - cmd 87/88

```
GET: 05 5A 02 00 57 00
SET: 05 5A 03 00 58 00 [mode]
```

| Valeur | Mode |
|--------|------|
| 0 | Off |
| 1 | On |

---

## Safe Max Volume - cmd 92/93

```
GET: 05 5A 02 00 5C 00
SET: 05 5A 03 00 5D 00 [max_vol]
```

---

## Commandes utilitaires

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

## Implementation dans technics.py

### Usage

```bash
uv run technics.py [-a MAC] [-c CANAL] [--raw] <commande> [args]
```

Sans argument apres la commande = GET (lecture). Avec argument = SET (ecriture).
`--raw` produit une sortie JSON pour scripting.

### Commandes disponibles

| Commande CLI | cmd_id | Description | GET | SET |
|-------------|--------|-------------|-----|-----|
| `status` | 240 | Tous les parametres (batch) | x | |
| `battery` | 3286+3329+64 | Batterie (agent/partner/boitier) | x | |
| `codec` | 18 | Info codec actuel | x | |
| `color` | 2 | Couleur appareil | x | |
| `anc [nc\|off\|ambient]` | 10/11 | Noise Canceling | x | x |
| `anc-level [0-40]` | 56/57 | Ajustement NC fin (dB) | x | x |
| `adaptive-anc [on\|off]` | 103/104 | ANC adaptatif | x | x |
| `ambient-mode [transparent\|attention]` | 33/34 | Mode ambiant (+ `--music`) | x | x |
| `outside-toggle [off,nc,ambient]` | 21/22 | Config bouton physique (bitmask) | x | x |
| `eq [off\|bass\|clear-voice\|...]` | 0x0901/0x0900 | Egaliseur (Airoha PEQ) | x | x |
| `spatial [on\|off]` | 99/100 | Audio spatial (+ `--head-tracking`) | x | x |
| `multipoint [off\|on\|triple]` | 50/51 | Multipoint Bluetooth | x | x |
| `switch-playing [on\|off]` | 85/86 | Bascule pendant la lecture | x | x |
| `ringtone-talking [on\|off]` | 87/88 | Sonnerie pendant appel | x | x |
| `auto-power-off [on\|off]` | 6/7 | Arret auto (+ `--minutes`) | x | x |
| `led [on\|off]` | 19/20 | LED clignotante | x | x |
| `wearing [on\|off]` | 77/78 | Detection de port (+ `--music/--touch/--replay`) | x | x |
| `assistant [google\|alexa\|off]` | 8/9 | Assistant vocal | x | x |
| `le-audio [on\|off]` | 89/90 | LE Audio | x | x |
| `noise-reduction [normal\|high]` | 52/53 | Reduction bruit appel | x | x |
| `buffer [auto\|music\|video]` | 58/59 | Buffer audio/video | x | x |
| `safe-volume [valeur]` | 92/93 | Volume max securise | x | x |
| `language [ja\|en\|de\|fr\|...]` | 37/5 | Langue des annonces (GET via getLangRev) | x | x |
| `jmv [on\|off\|start]` | 45/46/47 | Just My Voice | x | x |
| `vp-outside [tone\|voice]` | 69 | Annonce changement ANC | | x |
| `vp-connected [0-7]` | 70 | Annonce de connexion | | x |
| `vp-volume [volume]` | 68 | Volume annonces vocales | | x |
| `a2dp [sbc\|aac\|aptx\|ldac\|...]` | 16/17 | Preference codec Bluetooth | x | x |
| `tws-battery` | 3286+3329 | Batterie TWS (alias de battery) | x | |
| `connected-devices` | 73 | Appareils connectes | x | |
| `firmware-info` | 769/7688 | Infos firmware (SDK + build) | x | |
| `find-me` | 32 | Localiser (`--blink/--ring/--target`) | | x |
| `power-off` | 66 | Eteindre les ecouteurs | | x |

### Architecture

- **Registre generique** : 14 commandes simples (1 octet GET/SET) via `CmdDef` + `generic_get/set`
- **Fonctions specialisees** : 21 commandes complexes (multi-champs, bitmask, cmd systeme)
- **Batch** : `status` utilise la commande 240 pour recuperer ~20 parametres en une requete
- **CLI** : argparse avec 34 sous-commandes, aide en francais
- **GUI** : interface graphique customtkinter (voir section dediee)

### Interface graphique (technics_gui.py)

```bash
uv run technics_gui.py
```

Interface graphique customtkinter (theme sombre, 900x650) exposant toutes les fonctionnalites de `technics.py`. Dependance PEP 723 : `customtkinter>=5.2`.

**Architecture** :

```
App (CTk) : header, sidebar (8 boutons), content, status bar
  |-- BTWorker : thread daemon + threading.Lock pour ops RFCOMM
  |-- 8 pages (CTkScrollableFrame) :
  |     Batterie, ANC, Audio, Connexion, Reglages, Voix, Infos, Outils
  |-- Widgets reutilisables : Section, ToggleRow
```

**Modele de threading** : Toutes les operations Bluetooth tournent dans un thread daemon via `BTWorker`. Les callbacks UI utilisent `app.after(0, callback)` pour la thread-safety tkinter. Un `threading.Lock` serialise les acces au socket RFCOMM. Chaque page utilise un flag `_loading` pendant le refresh pour empecher les callbacks de widgets de declencher des commandes BT.

**Pages** :

| Page | Fonctionnalites | Commandes utilisees |
|------|-----------------|---------------------|
| Batterie | 3 barres (agent/partner/boitier), couleur dynamique | `cmd_battery_get` (agent via 3286, partner via relay 3329, cradle via 64) |
| ANC | Mode, niveau NC (slider), adaptatif, ambiant, bouton physique | `cmd_anc_get/set`, `cmd_anc_level_get/set`, `cmd_ambient_mode_get/set`, `cmd_outside_toggle_get/set`, generic adaptive-anc |
| Audio | EQ (9 presets), spatial, head tracking, codec A2DP, buffer, codec actuel | `cmd_spatial_get/set`, `cmd_codec_get`, generic eq/a2dp/buffer |
| Connexion | Multipoint, LE Audio, bascule lecture, liste appareils | `cmd_connected_devices_get`, generic multipoint/le-audio/switch-playing |
| Reglages | LED, detection port (4 sous-options), arret auto, volume securise, langue, sonnerie | `cmd_wearing_get/set`, `cmd_auto_power_off_get/set`, generic led/safe-volume/language/ringtone-talking |
| Voix | Assistant vocal, reduction bruit, annonces ANC/connexion, volume annonces, JMV | `cmd_vp_outside_set`, `cmd_vp_connected_set`, `cmd_vp_volume_set`, `cmd_jmv_start`, generic assistant/noise-reduction/jmv |
| Infos | Firmware (SDK, SoC, build), couleur, status JSON complet | `cmd_firmware_info_get`, `cmd_color_get`, `cmd_status_batch` |
| Outils | Localiser (blink/ring/cible), extinction avec confirmation | `cmd_find_me`, `cmd_power_off` |

**Flux utilisateur** :

1. Lancement → fenetre avec sidebar + page Batterie
2. Clic "Connecter" → thread BT → indicateur vert si OK
3. Auto-chargement `cmd_status_batch()` pour remplir toutes les pages
4. Navigation sidebar → `page.refresh()` charge les donnees specifiques
5. Changement de reglage → thread BT SET → feedback dans la status bar
6. "Deconnecter" → ferme le socket, remet l'indicateur rouge

### Commandes non implementees (debug/interne)

Ces commandes du protocole RACE ne sont pas exposees dans `technics.py` car elles relevent du diagnostic, de la fabrication ou de fonctionnalites avancees rarement utiles :

| cmd_id | Fonction | Raison |
|--------|----------|--------|
| 0/1 | Model ID | L'appareil est deja connu |
| 3 | Color SET | Couleur physique, non modifiable logiciellement |
| 23-27 | Key Enable / Keymap | Configuration avancee des boutons |
| 35/36 | Wearing Detection v1 | Remplace par v3 (cmd 77/78) |
| 37 | Language Revision (getLangRev) | **Utilise pour GET langue** (remplace cmd 4 defaillant) |
| 38-40 | VTrigger Lang / Revision | Revision firmware des langues vocales trigger |
| 41-43 | Erase/Log Output | Gestion de logs internes |
| 44 | Sensor Info | Donnees capteurs brutes |
| 48 | Fix Outside Ctrl | Commande interne |
| 54/55 | BT Info / Quality Info | Diagnostic Bluetooth |
| 65 | Factory Reset | Dangereux, non expose volontairement |
| 67 | VP Settings GET | Lecture seule des VP, peu utile |
| 71/72 | VP Play / Fix VP | Commandes internes |
| 74/75 | Demo Mode | Mode demonstration usine |
| 76 | Usage Time | Compteur d'utilisation |
| 79-82 | Wearing Test | Test de calibration capteur |
| 83/84 | Charge Error | Diagnostic de charge |
| 91 | Current Status | Etat interne non documente |
| 94/95 | Board/Mesh Info | Info carte/mesh |
| 97 | Cradle Version | Version firmware boitier |
| 98 | Usage Guide | Non documente |
| 101/102 | Dolby | Dolby non supporte sur AZ100 |

---

## Commandes Airoha (non Panasonic, non standard RACE)

### Airoha PEQ (Parametric EQ) - cmd 0x0901 GET / 0x0900 SET

Sur AZ100, l'EQ est controle via les commandes Airoha PEQ et non via les commandes Panasonic 12/13.

#### GET - cmd 2305 (0x0901)

```
Envoi:  05 5A 04 00 01 09 00 00       (payload = module_id LE = 0x0000)
Reponse: 05 5B LL LL 01 09 [status] [module_id_lo] [module_id_hi] [eq_idx]
```

| Champ | Description |
|-------|-------------|
| module_id | 0x0000 (toujours) |
| eq_idx | Index du mode EQ actif (meme mapping que Sound Mode cmd 12) |

#### SET - cmd 2304 (0x0900)

```
Envoi:  05 5A 05 00 00 09 00 00 [eq_idx]  (module_id LE + eq_idx)
Reponse: 05 5B LL LL 00 09 [status]
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

Source decompilee : `AirohaPeqMgr.java`, `PeqStageLoadUiData.java`, `PeqStageSetPeqGrpIdx.java`

---

## Mecanisme des indications (0x5D)

Certaines commandes ne retournent pas leurs donnees dans une reponse classique (0x5B) mais via une **indication** (0x5D). La reponse 0x5B sert alors uniquement d'ACK.

### Commandes concernees

| cmd_id | Fonction | Le 0x5B contient | Le 0x5D contient |
|--------|----------|-------------------|-------------------|
| 37 | getLangRev | ACK (status=0) | lang_byte, version string |
| 3286 | TWS Battery | ACK (status=0, data partielle) | status, agent_or_client, battery_percent |

### Filtrage dans send_recv

Le parametre `expected_type` de `send_recv()` permet de filtrer le type de paquet attendu :
- `expected_type=0x5B` (defaut) : retourne la premiere reponse 0x5B
- `expected_type=0x5D` : ignore les 0x5B intermediaires, retourne la premiere indication 0x5D

---

## Notes d'implementation

1. **Byte order** : TOUT est little-endian (length, cmd_id). C'est la cause principale d'echec si ignore.

2. **Conservation des niveaux** : Pour SET_OUTSIDE_CTRL, toujours lire les niveaux actuels via GET d'abord, puis les renvoyer avec le nouveau mode. Envoyer des valeurs arbitraires provoque un echec (status=1).

3. **Pas de handshake** : Aucune sequence d'initialisation requise. La connexion RFCOMM suffit, les commandes RACE peuvent etre envoyees immediatement.

4. **Timeout** : Les reponses arrivent generalement en < 500ms. Un timeout de 3 secondes est largement suffisant.

5. **Canal 21** : Le canal RFCOMM pour RACE est 21 sur cet appareil. Le canal 2 accepte les connexions mais ne repond pas aux commandes RACE.

6. **BLE non disponible** : Sur Windows, quand les ecouteurs sont connectes en Bluetooth Classic (pour l'audio), le GATT BLE n'est pas accessible. Utiliser RFCOMM uniquement.

7. **Execution Windows** : Les scripts doivent tourner cote Windows (pas WSL) car le Bluetooth est gere par Windows. Utiliser `uv run` pour l'execution sans venv. Depuis WSL, les fichiers sont accessibles via `\\wsl.localhost\Debian\...`.

8. **Commandes Panasonic vs Airoha** : Certaines commandes Panasonic (cmd 4 GET langue, cmd 12/13 EQ) ne fonctionnent pas correctement sur AZ100. Les equivalents Airoha (cmd 37 getLangRev, cmd 0x0901/0x0900 PEQ) doivent etre utilises a la place. Le SET reste souvent fonctionnel via la commande Panasonic (cmd 5 pour la langue).

9. **Indications vs Reponses** : Certaines commandes (3286, 37) retournent leurs donnees dans des indications 0x5D et non dans des reponses 0x5B. Le 0x5B sert alors d'ACK. Il faut filtrer par type de paquet attendu.

10. **Relay TWS** : Le partner (2eme ecouteur) n'est pas directement accessible. Les commandes doivent etre relayees via cmd 3329 (RELAY_PASS_TO_DST) avec un prefixe Dst obtenu via cmd 3328 (GetAvaDst). La reponse relay encapsule un paquet RACE interne.

---

## Errata et corrections

Les commandes Panasonic documentees dans le tableau initial ont ete validees experimentalement.
Certaines ne fonctionnent pas comme prevu sur AZ100 et ont du etre remplacees par des equivalents Airoha :

| Commande Panasonic | Probleme sur AZ100 | Solution |
|--------------------|---------------------|----------|
| cmd 4 (GET langue) | Retourne toujours 1 ("en") | Utiliser cmd 37 (getLangRev), indication 0x5D |
| cmd 12/13 (Sound Mode EQ) | GET retourne toujours 0, SET sans effet | Utiliser Airoha PEQ cmd 0x0901/0x0900 |
| cmd 3074 (Battery Level) | Aucune reponse | Utiliser cmd 3286 avec payload + relay 3329 pour partner |

---

## Sources

- APK Technics Audio Connect v4.3.1 decompile avec jadx 1.5.1
- Package `com.airoha.libbase.RaceCommand` (format RACE, packets)
- Package `com.airoha.libbase.RaceCommand.constant` (RaceId, RaceIdPana)
- Package `com.airoha.libbase.RaceCommand.packet.pana` (commandes Panasonic)
- Package `com.airoha.libmmi.stage.pana` (stages de commande avec payloads)
- Package `com.airoha.libpeq` (PEQ stages, AirohaPeqMgr)
- Package `com.airoha.libbase.relay` (Dst, RaceCmdRelayPass, RaceCmdGetAvaDst)
- Package `com.airoha.libmmi1562.stage` (MmiStageTwsGetBattery, MmiStageTwsGetBatteryRelay, MmiStageGetAvaDst)
- Package `com.airoha.libbase.constant` (AgentPartnerEnum)
- Package `com.panasonic.audioconnect.airoha.data` (DeviceMmiConstants, OutsideCtrl)
- RACE Toolkit : https://github.com/auracast-research/race-toolkit
- ERNW White Paper 74 : Airoha RACE Bluetooth Headphone Vulnerabilities
