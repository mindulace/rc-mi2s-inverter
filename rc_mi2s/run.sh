#!/usr/bin/with-contenv bashio
# Broker access comes automatically from the HA MQTT service (services: mqtt:need)
export MQTT_HOST="$(bashio::services mqtt 'host')"
export MQTT_PORT="$(bashio::services mqtt 'port')"
export MQTT_USER="$(bashio::services mqtt 'username')"
export MQTT_PASSWORD="$(bashio::services mqtt 'password')"
export SERIAL="$(bashio::config 'serial')"
export SEND_TIMESYNC="$(bashio::config 'send_timesync')"
export FORWARD_HOST="$(bashio::config 'forward_host')"
export FORWARD_PORT="$(bashio::config 'forward_port')"

bashio::log.info "RC MI2S Inverter bridge -> ${MQTT_HOST}:${MQTT_PORT} (serial='${SERIAL}', timesync=${SEND_TIMESYNC}, forward='${FORWARD_HOST}')"
exec /opt/venv/bin/python3 /bridge.py
