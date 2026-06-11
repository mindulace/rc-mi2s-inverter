# RC MI2S Inverter — Home Assistant add-on repository

Local, **cloud-free** Home Assistant integration for the **RC MI2S-800D**
microinverter (sold under RC / Rockcore; cloud `rc-ess.com`; app "RC-C";
internal MQTT platform `jowoiot`).

The inverter ships only with a Chinese cloud and has no official Home Assistant
integration. It does, however, talk plain MQTT to its cloud. This add-on points
the inverter at your **own** Mosquitto broker, decodes the telemetry and exposes
it to Home Assistant via MQTT discovery — fully local, no cloud.

## Add-ons in this repository
- **[RC MI2S Inverter](./rc_mi2s)** — the bridge add-on (MQTT decoder + HA discovery).

## Installation
1. In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**.
2. Add this repository URL:
   ```
   https://github.com/mindulace/rc-mi2s-inverter
   ```
3. Install **RC MI2S Inverter** from the store and follow its documentation.

See the add-on [README](./rc_mi2s/README.md) for the Mosquitto login, DNS/firewall
redirect and configuration.

## Hardware / protocol notes
- Wi-Fi module: Hi-Flying **HF-LPT270** (transparent serial↔TCP bridge); the
  inverter MCU speaks MQTT over it.
- Cloud endpoint: `www.eur-mq.rc-ess.com:1883` (plain MQTT, no TLS).
- Telemetry topic: `jowoiot/toServer/v2/<serial>`, JSON key/value.
- The microinverter needs ~24–50 V input (MPPT 30–45 V): pair two panels in
  series per input.

## Status / contributing
The telemetry key mapping was reverse-engineered from a capture. Confirmed:
`pa1`/`pb1` = per-string power (W), `p1` = AC voltage, `p2` = grid frequency,
`g5` = DC voltage. Several keys (`pa2/pb2`, `pa3/pb3`, `p3–p8`, `g1–g4`) are not
yet identified — PRs welcome.

## License
MIT — see [LICENSE](./LICENSE).
