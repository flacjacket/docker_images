FROM homeassistant/home-assistant:2021.12.8

COPY docker-healthcheck.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-healthcheck.sh

COPY *.patch /
RUN  cd /usr/src/homeassistant/ \
  && for p in /*.patch; do git apply $p; done \
  && rm /*.patch

RUN addgroup -g 1000 home_assistant \
 && adduser -D -u 1000 -h /config -G home_assistant home_assistant \
 && adduser home_assistant audio \
 && chmod +x /etc/services.d/home-assistant/run \
 && chmod +x /etc/services.d/home-assistant/finish

RUN mkdir -p /static_config/custom_components
RUN mkdir /static_config/custom_components/hacs && \
    wget "https://github.com/hacs/integration/releases/latest/download/hacs.zip" && \
    wget "https://github.com/custom-components/alexa_media_player/releases/download/v3.10.15/alexa_media.zip" && \
    wget "https://github.com/zachowj/hass-node-red/archive/v1.0.5.zip" -O hass-node-red.zip && \
    wget "https://github.com/AlexxIT/WebRTC/archive/refs/heads/master.zip" -O webrtc.zip && \
    wget "https://github.com/blakeblackshear/frigate-hass-integration/archive/refs/tags/v2.2.0.zip" -O frigate.zip && \
    unzip hacs.zip -d /static_config/custom_components/hacs && \
    unzip alexa_media.zip -d /static_config/custom_components/alexa_media && \
    unzip hass-node-red.zip && \
    unzip webrtc.zip && \
    unzip frigate.zip && \
    mv hass-node-red-*/custom_components/nodered /static_config/custom_components/ && \
    mv WebRTC-*/custom_components/webrtc /static_config/custom_components/ && \
    mv frigate-hass-integration-*/custom_components/frigate /static_config/custom_components/ && \
    rm -r *.zip hass-node-red-*/ WebRTC-*/ frigate-hass-integration-*/
COPY *.yaml /static_config/
COPY automations /static_config/automations
COPY custom_components /static_config/custom_components
COPY scripts /static_config/scripts
RUN chmod 444 /static_config/*.yaml
RUN python -m pip install --force-reinstall --no-deps \
    https://github.com/flacjacket/python-amcrest/archive/py3.tar.gz

HEALTHCHECK CMD /usr/local/bin/docker-healthcheck.sh || exit 1
