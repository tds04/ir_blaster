# IR Blaster — Home Assistant HACS Integration

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tds04&repository=ir_blaster&category=integration)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/tds04/ir_blaster)

> Local control for Tuya IR blasters (PID: zG1yTHAcRg5YvqyA) via Tasmota MQTT — no cloud required.

Local control integration for the RSH-Smart-IR V6 IR blaster board (sold under various brand names). Replaces Tuya cloud with full local control via Tasmota and MQTT.

The board uses a dedicated IR MCU for all transmission and reception, with a TYWE3S (ESP8266) WiFi module acting as a UART bridge. This integration talks to Tasmota running on the TYWE3S via MQTT, exposing study/learn mode and IR code transmission to Home Assistant.

**Reverse engineered via UART traffic analysis — no Tuya cloud, no app, no account required.**

## Supported Hardware

- Board: RSH-Smart-IR V6 (2018)
- WiFi module: TYWE3S (ESP8266, 1MB)
- IR MCU: Dedicated on-board controller
- UART: 9600 baud, Tuya MCU serial protocol
- Tuya Product ID: `zG1yTHAcRg5YvqyA`
- Tuya Product Code: `IRREMOTEWFBK`

## Requirements

- Home Assistant with MQTT integration configured
- Tasmota flashed to the device's WiFi module (TYWE3S)
- MQTT broker (e.g. Mosquitto)

## Tasmota Setup

Flash Tasmota lite to the TYWE3S module. In the Tasmota console:

```
Backlog Template {"NAME":"Tuya IR","GPIO":[0,0,0,0,0,0,0,0,0,0,0,0,0],"FLAG":0,"BASE":54}; Module 0
Baudrate 9600
SetOption66 1
Topic Irblaster
```

Configure MQTT in **Configuration → Configure MQTT** to point to your broker.

## Installation via HACS

1. In HACS → Integrations → Custom Repositories
2. Add `https://github.com/tds04/ir_blaster` as type **Integration**
3. Install **IR Blaster**
4. Restart Home Assistant
5. Settings → Devices & Services → Add Integration → **IR Blaster**
6. Enter your device name and Tasmota MQTT topic

## Entities Created

| Entity | Type | Purpose |
|--------|------|---------|
| `sensor.ir_blaster_last_captured_code` | Sensor | Last IR code captured during study mode |
| `switch.ir_blaster_study_mode` | Switch | Toggle study/learn mode on/off |
| `text.ir_blaster_code_name` | Text | Type a name here before pressing Learn |
| `text.ir_blaster_send_code` | Text | Write any hex code directly to fire IR |
| `button.ir_blaster_learn` | Button | Start learning a new code |
| `button.ir_blaster_send_last_captured` | Button | Resend last captured code (test) |
| `button.ir_blaster_<name>` | Button | One per saved code — fires that IR code |

## Learning New Codes

All learning happens directly on the device card — no config menus needed.

1. Find the **Code Name** text field on the device card
2. Type a name for the button (e.g. `Fireplace On`, `TV Power`)
3. Press the **Learn** button
4. Point your remote at the IR blaster and press the button within 30 seconds
5. A notification confirms the code was captured and saved
6. A new button appears on the device card — press it to fire that IR code

Repeat for each button you want to control. Codes are stored persistently and survive HA restarts.

## Testing

Use **Send Last Captured** to verify the full pipeline:
1. Toggle **Study Mode** ON
2. Point remote, press button — sensor updates
3. Toggle **Study Mode** OFF
4. Press **Send Last Captured** — IR fires

## Sending Codes via Automation

Write directly to the `text.ir_blaster_send_code` entity:

```yaml
service: text.set_value
target:
  entity_id: text.ir_blaster_send_code
data:
  value: "4C8D405187FDFCB60B55835B..."
```

## Technical Details

This device uses a dedicated IR MCU that handles all IR transmission and reception. The TYWE3S WiFi module communicates with the IR MCU over UART at 9600 baud using the Tuya serial protocol (55 AA framing).

Key packet sequences discovered by reverse engineering:

| Action | Packet |
|--------|--------|
| Study On | `SerialSend5 55AA000600050104000101 11` |
| Study Off | `SerialSend5 55AA000600050104000102 12` |
| Send IR |  `55AA000600050100000100 0C` + DP7 code |

IR codes are 80 bytes raw, prefixed with Tuya framing. They come back from the MCU on DP2 or DP7 via `TuyaReceived` MQTT message.

## Credits

Reverse engineered from IRREMOTEWFBK using TuyaMCU Explorer/Analyzer and Waveshare USB serial adapter. Protocol documented through extensive UART traffic analysis.

