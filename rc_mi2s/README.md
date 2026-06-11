# RC MI2S Inverter (Home Assistant add-on)

Local, **cloud-free** bridge for the **RC MI2S-800D** microinverter (sold under
RC / Rockcore, cloud `rc-ess.com`, app "RC-C", internal MQTT platform
`jowoiot`). It reads the inverter's MQTT telemetry from your local Mosquitto,
decodes it and exposes the values as Home Assistant sensors via MQTT discovery —
**no manufacturer cloud involved**. Optional forwarding keeps the original app
working.

> ⚠️ **Unmaintained — no support, no warranty.** Personal reverse-engineering
> project, shared as-is. Not actively maintained; it may break with firmware or
> Home Assistant changes. **Use at your own risk.** Forks/PRs welcome, issues may
> go unanswered.

## Requirements
- Home Assistant with the **Mosquitto broker** add-on (your existing one is fine).
- A way to redirect the inverter to your broker (DNS override + firewall, below).

## How it works
The inverter is an MQTT client that publishes to `jowoiot/toServer/v2/<serial>`
and subscribes to `jowoiot/toEdge/<serial>`. This bridge:
1. subscribes to the telemetry, decodes the `{"data":[{"k":..,"v":..}]}` JSON and
   publishes HA-discovery sensors;
2. answers on `toEdge` for **every** message — a content-based handshake the
   inverter requires (`register` echoing its `g4` value to complete
   registration, `err` for flag groups, `save` otherwise). Without a prompt
   reply the inverter stays stuck and keeps reconnecting.

The serial number is **auto-detected** from the topic, so no configuration is
required for it to work.

## Sensors
Exposed under the device **"RC MI2S Inverter \<serial\>"**:

| Sensor | Unit | Source |
|--------|------|--------|
| PV1–PV4 Power | W | per-string DC power |
| PV1–PV4 Voltage | V | per-string DC voltage (shared MPPT) |
| PV1–PV4 Current | A | derived (power ÷ voltage) |
| Total PV Power | W | sum of strings |
| AC Power | W | output power (updates every ~15 min) |
| AC Voltage | V | grid voltage |
| Grid Frequency | Hz | grid frequency |
| Temperature | °C | inverter temperature |
| Signal Strength | % | Wi-Fi signal |

Unused inputs (e.g. PV3/PV4) simply report 0.

### Energy dashboard
The device's internal energy counter carries a factory offset, so use a
**Riemann sum integral helper** on *Total PV Power* (metric prefix `k`, time
unit `h`) to get a clean kWh sensor, then add it under
*Settings → Dashboards → Energy → Solar production*.

## Setup

### 1. Allow the inverter's login in Mosquitto
The inverter has hard-coded credentials (`client` / `client`) that cannot be
changed. Add them in **Mosquitto add-on → Configuration** and restart Mosquitto:
```yaml
logins:
  - username: client
    password: client
```
The bridge itself needs no credentials — it gets broker access from the HA MQTT
service automatically.

### 2. Redirect the inverter to your broker (reset-proof)
- **DNS override** on your router: `www.eur-mq.rc-ess.com` → your HA/Mosquitto IP.
- **Firewall**: allow the inverter's network → Mosquitto `:1883`.
- Soft-restart the inverter's Wi-Fi module (`http://<inverter-ip>/` → restart) so
  it drops the cached cloud IP.

### 3. Start the add-on
Watch the log for `update: {...}` lines. The sensors appear under the device.

## Options
| Option          | Default | Meaning |
|-----------------|---------|---------|
| `serial`        | (empty) | Restrict to one device serial. Empty = auto-detect all. |
| `send_timesync` | `true`  | Send the `toEdge` handshake/time-sync replies. Leave on (turn off only to debug). |
| `forward_host`  | (empty) | Forward telemetry to the real cloud so the manufacturer app keeps working. Use the cloud **IP** (e.g. `47.237.20.177`), **not** the hostname — your DNS override points the hostname back to the local broker (that would loop). Empty = off. |
| `forward_port`  | `1883`  | Cloud port for forwarding. |

When forwarding is enabled, the bridge relays both directions and lets the cloud
answer `toEdge` (local emulation pauses). If the cloud host is unreachable it
falls back to local emulation. Find the current cloud IP with
`nslookup www.eur-mq.rc-ess.com` from a device **without** the DNS override.

## Notes
- After redirecting, the manufacturer app only works if `forward_host` is set.
- All telemetry keys were reverse-engineered and verified against the app.
  Static config/limit groups (`ctrl1_*`) and unused fields (`p3`, `p8`,
  `g1`–`g6`) are intentionally not exposed.
