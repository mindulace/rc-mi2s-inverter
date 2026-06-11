# RC MI2S Inverter (Home Assistant add-on)

Local, **cloud-free** bridge for the **RC MI2S-800D** microinverter (sold under
RC / Rockcore, cloud `rc-ess.com`, app "RC-C", internal MQTT platform
`jowoiot`). It reads the inverter's MQTT telemetry from your local Mosquitto,
decodes it and exposes the values as Home Assistant sensors via MQTT discovery —
**no manufacturer cloud involved**.

## Requirements
- Home Assistant with the **Mosquitto broker** add-on (your existing one is fine).
- A way to redirect the inverter to your broker (see below).

## How it works
The inverter is an MQTT client that publishes to `jowoiot/toServer/v2/<serial>`
and subscribes to `jowoiot/toEdge/<serial>`. This bridge:
1. subscribes to the telemetry, decodes the `{"data":[{"k":..,"v":..}]}` JSON and
   publishes HA-discovery sensors (PV1..PV4 power, total power, AC voltage, grid
   frequency, DC voltage);
2. replies on `toEdge` immediately for every message (time sync) — without that
   prompt reply the inverter keeps reconnecting.

The serial number is **auto-detected** from the topic, so no configuration is
required for it to work.

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
Watch the log for `update: {...}` lines. The sensors appear under the device
**"RC MI2S Inverter <serial>"**.

## Options
| Option          | Default | Meaning |
|-----------------|---------|---------|
| `serial`        | (empty) | Restrict to one device serial. Empty = auto-detect all. |
| `send_timesync` | `true`  | Send the `toEdge` time-sync reply (recommended; turn off only to debug). |

## Notes
- After redirecting, the **manufacturer app stops working** (intended — local only).
- Key mapping (`pa1`=PV1 W, `pb1`=PV2 W, `p1`=AC V, `p2`=Hz, `g5`=DC V) was derived
  from a capture. Unmapped fields (`pa2/pb2`, `pa3/pb3`, `p3–p8`, `g1–g4`) are not
  exposed yet. Contributions welcome.
