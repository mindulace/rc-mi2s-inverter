#!/usr/bin/env python3
"""
RC MI2S Inverter bridge — RC MI2S-800D (the "jowoiot" platform) -> Home Assistant.

Connects as an MQTT client to the (local) Mosquitto broker, subscribes to the
inverter telemetry (jowoiot/toServer/v2/<serial>), decodes the key/value JSON
and exposes the values as Home Assistant sensors via MQTT discovery. The serial
number is auto-detected from the topic, so it works without configuration for
any number of devices. The optional `serial` option restricts it to one device.

The bridge also replies on toEdge immediately for every telemetry message
(time sync). Without that prompt reply the inverter considers the server dead
and keeps reconnecting.

Note: `jowoiot/...` is the device's fixed topic namespace (baked into the
firmware, cannot be changed). `rc_mi2s/...` is this bridge's own namespace for
the decoded/republished state.

Configuration via environment (run.sh fills these from the add-on options):
    MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD  (from the HA MQTT service)
    SERIAL          optional: only accept this device (empty = all)
    SEND_TIMESYNC   "true" / "false"
"""
import json
import os
import time

import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "core-mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER") or None
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD") or None
SERIAL_FILTER = (os.environ.get("SERIAL") or "").strip()   # empty = all devices
SEND_TIMESYNC = (os.environ.get("SEND_TIMESYNC", "true").lower() == "true")

# Optional forwarding to the real cloud so the manufacturer app keeps working.
# Use the cloud's IP (e.g. 47.237.20.177) — NOT the hostname, which your DNS
# override points back to the local broker (that would loop). Empty = off.
FORWARD_HOST = (os.environ.get("FORWARD_HOST") or "").strip()
FORWARD_PORT = int(os.environ.get("FORWARD_PORT", "1883"))
FORWARDING = bool(FORWARD_HOST)

DISCOVERY_PREFIX = "homeassistant"
TELEMETRY_WILDCARD = "jowoiot/toServer/v2/+"   # device-fixed namespace

# Telemetry key -> (sensor_id, friendly name, factor, unit, device_class).
# Confirmed from a capture: pa1/pb1 = live per-string power (W),
# p1 = AC voltage, p2 = grid frequency (/100), g5 = DC voltage (/100).
SENSORS = {
    "pa1": ("pv1_power",   "PV1 Power",      1.0,  "W",  "power"),
    "pb1": ("pv2_power",   "PV2 Power",      1.0,  "W",  "power"),
    "pc1": ("pv3_power",   "PV3 Power",      1.0,  "W",  "power"),
    "pd1": ("pv4_power",   "PV4 Power",      1.0,  "W",  "power"),
    "pa2": ("pv1_voltage", "PV1 Voltage",    0.5,  "V",  "voltage"),
    "pb2": ("pv2_voltage", "PV2 Voltage",    0.5,  "V",  "voltage"),
    "pc2": ("pv3_voltage", "PV3 Voltage",    0.5,  "V",  "voltage"),
    "pd2": ("pv4_voltage", "PV4 Voltage",    0.5,  "V",  "voltage"),
    "p1":  ("ac_voltage",     "AC Voltage",      1.0,  "V",  "voltage"),
    "p2":  ("frequency",      "Grid Frequency",  0.01, "Hz", "frequency"),
    "p4":  ("temperature",    "Temperature",     1.0,  "°C", "temperature"),
    "p7":  ("signal_strength", "Signal Strength", 1.0,  "%",  None),
}
PV_POWER_IDS = ("pv1_power", "pv2_power", "pv3_power", "pv4_power")

# Derived sensors (computed, not raw keys): per-string current = power / voltage,
# plus total power. Published to discovery in addition to SENSORS.
DERIVED = {
    "pv1_current": ("PV1 Current", "A", "current"),
    "pv2_current": ("PV2 Current", "A", "current"),
    "pv3_current": ("PV3 Current", "A", "current"),
    "pv4_current": ("PV4 Current", "A", "current"),
    "total_power": ("Total PV Power", "W", "power"),
}
# Sensor ids published by older versions — cleared from discovery on connect.
REMOVED_SENSOR_IDS = ("dc_voltage",)

states = {}         # serial -> {sensor_id: value}
discovered = set()  # serials with published discovery

_local_client = None              # set in main(), used to relay cloud -> inverter
_cloud = {"client": None, "serial": None}   # second connection for forwarding


def now_ms():
    return int(time.time() * 1000)


def state_topic(serial):
    return f"rc_mi2s/{serial}/state"


def avail_topic(serial):
    return f"rc_mi2s/{serial}/availability"


def toedge_topic(serial):
    return f"jowoiot/toEdge/{serial}"   # device-fixed namespace


def device_block(serial):
    return {
        "identifiers": [f"rc_mi2s_{serial}"],
        "name": f"RC MI2S Inverter {serial}",
        "manufacturer": "RC / Rockcore",
        "model": "MI2S-800D",
    }


def _sensor_config(serial, sid, name, unit, dclass):
    cfg = {
        "name": name,
        "unique_id": f"rc_mi2s_{serial}_{sid}",
        "state_topic": state_topic(serial),
        "value_template": "{{ value_json.%s }}" % sid,
        "unit_of_measurement": unit,
        "state_class": "measurement",
        "availability_topic": avail_topic(serial),
        "device": device_block(serial),
    }
    if dclass:                       # signal strength etc. have no device_class
        cfg["device_class"] = dclass
    return cfg


def publish_discovery(client, serial):
    for _key, (sid, name, _f, unit, dclass) in SENSORS.items():
        client.publish(f"{DISCOVERY_PREFIX}/sensor/rc_mi2s_{serial}/{sid}/config",
                       json.dumps(_sensor_config(serial, sid, name, unit, dclass)), retain=True)
    for sid, (name, unit, dclass) in DERIVED.items():
        client.publish(f"{DISCOVERY_PREFIX}/sensor/rc_mi2s_{serial}/{sid}/config",
                       json.dumps(_sensor_config(serial, sid, name, unit, dclass)), retain=True)
    for sid in REMOVED_SENSOR_IDS:   # delete stale entities from older versions
        client.publish(f"{DISCOVERY_PREFIX}/sensor/rc_mi2s_{serial}/{sid}/config", "", retain=True)
    client.publish(avail_topic(serial), "online", retain=True)
    print(f"[bridge] published discovery for {serial}", flush=True)


def serial_from_topic(topic):
    parts = topic.split("/")
    return parts[-1] if len(parts) >= 4 and parts[-1] else None


def send_response(client, serial, data, device_t):
    """Reply on toEdge for every message, mirroring the cloud's handshake.

    This is a request/response protocol: the inverter sends the registration
    group (g1..g6, contains g4) and stays stuck there until it receives a
    'register' ack that echoes its g4 value — only then does it stream the data
    groups. Flag groups (fa3/fb3) expect 'err', everything else 'save'.
    trecv echoes the device's meta.t (time sync), tsend = our real time.
    """
    if not SEND_TIMESYNC:
        return
    kv = {it.get("k"): it.get("v") for it in data}
    if "g4" in kv:
        rtype, rval = "register", kv["g4"]
    elif "fa3" in kv:
        rtype, rval = "err", kv["fa3"]
    else:
        rtype, rval = "save", "0"
    msg = {"type": rtype, "value": str(rval),
           "tsend": now_ms(),
           "trecv": device_t if device_t is not None else now_ms(),
           "interval": 30}
    client.publish(toedge_topic(serial), json.dumps(msg))
    print(f"[bridge] {serial} -> toEdge {rtype} value={rval}", flush=True)


def _cloud_on_connect(c, userdata, flags, rc):
    serial = userdata
    print(f"[forward] connected to cloud {FORWARD_HOST}:{FORWARD_PORT} (rc={rc})", flush=True)
    c.subscribe(f"jowoiot/toEdge/{serial}")


def _cloud_on_message(c, userdata, msg):
    # cloud -> inverter: relay the cloud's toEdge command to the local broker
    if _local_client is not None:
        _local_client.publish(f"jowoiot/toEdge/{userdata}", msg.payload)


def ensure_cloud(serial):
    """Open a second MQTT connection to the real cloud (once) and relay this
    device both ways, so the manufacturer app keeps working. We rely on the
    cloud's toEdge replies instead of our local emulation."""
    if not FORWARDING or _cloud["client"] is not None:
        return
    cc = mqtt.Client(client_id=serial, userdata=serial)
    cc.username_pw_set("client", "client")   # the device's hard-coded cloud login
    cc.on_connect = _cloud_on_connect
    cc.on_message = _cloud_on_message
    try:
        cc.connect(FORWARD_HOST, FORWARD_PORT, keepalive=60)
        cc.loop_start()
        _cloud["client"] = cc
        _cloud["serial"] = serial
        print(f"[forward] forwarding {serial} <-> cloud {FORWARD_HOST}:{FORWARD_PORT}", flush=True)
    except Exception as e:
        print(f"[forward] cloud connect failed: {e}", flush=True)


def on_connect(client, userdata, flags, rc):
    print(f"[bridge] connected to broker (rc={rc}) — subscribing {TELEMETRY_WILDCARD}", flush=True)
    client.subscribe(TELEMETRY_WILDCARD)


def on_message(client, userdata, msg):
    serial = serial_from_topic(msg.topic)
    if not serial:
        return
    if SERIAL_FILTER and serial != SERIAL_FILTER:
        return
    try:
        obj = json.loads(msg.payload.decode("utf-8", "replace"))
    except Exception:
        return

    if serial not in discovered:
        publish_discovery(client, serial)
        discovered.add(serial)

    data = obj.get("data", [])
    # Either relay to the cloud (so the app works) and let the cloud answer
    # toEdge, or answer toEdge ourselves locally. Falls back to local if the
    # cloud connection isn't up yet.
    forwarded = False
    if FORWARDING:
        ensure_cloud(serial)
        cc = _cloud["client"]
        if cc is not None and serial == _cloud["serial"]:
            cc.publish(f"jowoiot/toServer/v2/{serial}", msg.payload)
            forwarded = True
    if not forwarded:
        send_response(client, serial, data, obj.get("meta", {}).get("t"))

    st = states.setdefault(serial, {})
    updated = False
    for item in data:
        k, v = item.get("k"), item.get("v")
        if k in SENSORS:
            sid, _n, factor, _u, _d = SENSORS[k]
            try:
                st[sid] = round(float(v) * factor, 2)
                updated = True
            except (TypeError, ValueError):
                pass
    if updated:
        st["total_power"] = round(sum(st.get(s, 0) for s in PV_POWER_IDS), 1)
        # derive per-string current = power / voltage (matches the app exactly)
        for n in (1, 2, 3, 4):
            p = st.get(f"pv{n}_power")
            v = st.get(f"pv{n}_voltage")
            if p is not None and v:
                st[f"pv{n}_current"] = round(p / v, 2)
            elif p == 0:
                st[f"pv{n}_current"] = 0.0
        client.publish(state_topic(serial), json.dumps(st))
        print(f"[bridge] {serial} update: {st}", flush=True)


def main():
    global _local_client
    client = mqtt.Client(client_id="rc-mi2s-inverter-bridge")
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    _local_client = client
    fwd = f"{FORWARD_HOST}:{FORWARD_PORT}" if FORWARDING else "off"
    print(f"[bridge] starting — broker {MQTT_HOST}:{MQTT_PORT}, "
          f"filter={SERIAL_FILTER or 'all devices'}, timesync={SEND_TIMESYNC}, "
          f"forward={fwd}", flush=True)
    # If forwarding to a fixed device, open the cloud link up front so it is
    # ready to relay the registration group when the inverter (re)connects.
    if FORWARDING and SERIAL_FILTER:
        ensure_cloud(SERIAL_FILTER)
    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except Exception as e:
            print(f"[bridge] broker connection failed: {e} — retry in 5s", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
