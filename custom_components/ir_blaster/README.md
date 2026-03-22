# IR Blaster — Home Assistant HACS Integration

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
| `switch.ir_blaster_study_mode` | Switch | Toggle study/learn mode |
| `button.ir_blaster_study_on` | Button | Start study mode |
| `button.ir_blaster_study_off` | Button | Stop study mode |
| `text.ir_blaster_send_code` | Text | Write hex code here to fire IR |

## Workflow

### Capture a new code
1. Toggle **Study Mode** switch ON (or press **Study On** button)
2. Point your remote at the IR blaster and press the button
3. Red LED flashes — code captured
4. `sensor.ir_blaster_last_captured_code` updates with the hex string
5. Copy that value to an `input_text` helper to store it

### Send a code
Write the hex string to `text.ir_blaster_send_code` from any automation or script:

```yaml
service: text.set_value
target:
  entity_id: text.ir_blaster_send_code
data:
  value: "55AA000600540700005036..."
```

Or via MQTT directly:
```
cmnd/Irblaster/SerialSend5  55AA000600540700005036...
```

## Storing Codes

Add `input_text` helpers in HA for each button you want to control:

```yaml
# configuration.yaml
input_text:
  ir_tv_power:
    name: "IR - TV Power"
    max: 500
  ir_fireplace_on:
    name: "IR - Fireplace On"
    max: 500
```

Then use scripts to save and send:

```yaml
# Save last captured code
service: input_text.set_value
target:
  entity_id: input_text.ir_tv_power
data:
  value: "{{ states('sensor.ir_blaster_last_captured_code') }}"

# Send stored code
service: text.set_value
target:
  entity_id: text.ir_blaster_send_code
data:
  value: "{{ states('input_text.ir_tv_power') }}"
```

## Technical Details

This device uses a dedicated IR MCU that handles all IR transmission and reception. The TYWE3S WiFi module communicates with the IR MCU over UART at 9600 baud using the Tuya serial protocol (55 AA framing).

Key packet sequences discovered by reverse engineering:

| Action | Packet |
|--------|--------|
| Study On | `55AA000600050104000101 11` |
| Study Off | `55AA000600050104000102 12` |
| Send IR | `55AA000600050100000100 0C` + DP7 code |

IR codes are 80 bytes raw, prefixed with Tuya framing. They come back from the MCU on DP2 or DP7 via `TuyaReceived` MQTT message.

## Credits

Reverse engineered from IRREMOTEWFBK using TuyaMCU Explorer/Analyzer and Waveshare USB serial adapter. Protocol documented through extensive UART traffic analysis.
