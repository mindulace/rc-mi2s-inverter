# RC MI2S Inverter — Home Assistant add-on repository

Local, **cloud-free** Home Assistant integration for the **RC MI2S-800D**
microinverter (sold under RC / Rockcore; cloud `rc-ess.com`; app "RC-C";
internal MQTT platform `jowoiot`).

The inverter ships only with a Chinese cloud and has no official Home Assistant
integration. It does, however, talk plain MQTT to its cloud. This add-on points
the inverter at your **own** Mosquitto broker, decodes the telemetry and exposes
it to Home Assistant via MQTT discovery — fully local, no cloud. The original
manufacturer app can optionally be kept alive via forwarding.

> ⚠️ **Unmaintained — no support, no warranty.** This is a personal
> reverse-engineering project, published as-is in case it's useful to others.
> It is **not actively maintained**, there is no support, and it may break with
> firmware or Home Assistant changes. **Use at your own risk.** Forks and PRs are
> welcome, but issues may go unanswered. Nobody here is "the author/maintainer".

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
redirect, options and the full sensor list.

## What you get
A device **"RC MI2S Inverter \<serial\>"** with: per-string power / voltage /
current (PV1–PV4), total PV power, AC power, AC voltage, grid frequency,
inverter temperature and Wi-Fi signal strength. Add a Riemann integral on the
total power for the Energy dashboard.

## Hardware / protocol notes
- Wi-Fi module: Hi-Flying **HF-LPT270** (transparent serial↔TCP bridge); the
  inverter MCU speaks MQTT over it.
- Cloud endpoint: `www.eur-mq.rc-ess.com:1883` (plain MQTT, no TLS).
- Telemetry topic: `jowoiot/toServer/v2/<serial>`, JSON key/value; the device
  needs a `toEdge` handshake reply (`register`/`err`/`save`) or it won't stream.
- The microinverter needs ~24–50 V input (MPPT 30–45 V): pair two panels in
  series per input.

## Telemetry key map (reverse-engineered, verified against the app)
| Key(s) | Meaning | Scale |
|--------|---------|-------|
| `pa1`–`pd1` | per-string power | × 1 → W |
| `pa2`–`pd2` | per-string DC voltage | × 0.5 → V |
| `p1` | AC voltage | × 1 → V |
| `p2` | grid frequency | × 0.01 → Hz |
| `p4` | inverter temperature | × 1 → °C |
| `p5` | AC output power (900-group) | × 1 → W |
| `p7` | Wi-Fi signal strength | × 1 → % |
| `pa3`/`pb3`/`p6` | cumulative energy counters (factory offset) | ~Wh |
| `g1`–`g6` | registration/boot params (`g4` = register handshake value) | — |
| `ctrl1_*` | static protection/config limits | — |
| `p3`, `p8` | unused / zero | — |

## License
MIT — see [LICENSE](./LICENSE).
