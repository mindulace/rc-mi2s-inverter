ARG BUILD_FROM
FROM ${BUILD_FROM}

# Python + paho-mqtt (v1 API, matching bridge.py) in a venv
RUN apk add --no-cache python3 py3-pip \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir "paho-mqtt<2"

COPY run.sh /run.sh
COPY bridge.py /bridge.py
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
