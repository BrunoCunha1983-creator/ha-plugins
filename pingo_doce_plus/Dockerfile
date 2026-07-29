ARG BUILD_FROM=mcr.microsoft.com/playwright/python:v1.50.0-noble
FROM ${BUILD_FROM}

ARG BUILD_VERSION
ARG BUILD_ARCH

LABEL \
  io.hass.name="Pingo Doce Plus" \
  io.hass.description="Sessão persistente e recolha de dados do Pingo Doce para Home Assistant" \
  io.hass.arch="${BUILD_ARCH}" \
  io.hass.type="app" \
  io.hass.version="${BUILD_VERSION}"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    DISPLAY=:99 \
    TZ=Europe/Lisbon

RUN apt-get update && apt-get install -y --no-install-recommends \
      xvfb x11vnc novnc websockify openbox dbus-x11 ca-certificates \
      fonts-dejavu-core fonts-liberation fonts-noto-color-emoji procps tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/pingo-doce-plus
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY run.sh /run.sh
RUN chmod a+x /run.sh

EXPOSE 7900
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/run.sh"]
