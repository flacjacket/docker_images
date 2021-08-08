FROM homeassistant/home-assistant:2021.8.3

COPY docker-healthcheck.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-healthcheck.sh

RUN addgroup -g 1000 home_assistant \
 && adduser -D -u 1000 -h /config -G home_assistant home_assistant \
 && adduser home_assistant audio \
 && chmod +x /etc/cont-init.d/udev.sh \
 && chmod +x /etc/services.d/home-assistant/run \
 && chmod +x /etc/services.d/home-assistant/finish

RUN mkdir -p /static_config/custom_components
RUN mkdir /static_config/custom_components/hacs && \
    wget "https://github.com/hacs/integration/releases/latest/download/hacs.zip" && \
    unzip hacs.zip -d /static_config/custom_components/hacs && \
    wget "https://github.com/zachowj/hass-node-red/archive/v0.5.2.zip" -O hass-node-red.zip && \
    unzip hass-node-red.zip && \
    mv hass-node-red-*/custom_components/nodered /static_config/custom_components/ && \
    rm -r *.zip hass-node-red-*/
COPY *.yaml /static_config/
COPY automations /static_config/automations
COPY custom_components /static_config/custom_components
RUN chmod 444 /static_config/*.yaml
RUN python -m pip install --force-reinstall --no-deps \
    https://github.com/flacjacket/python-amcrest/archive/py3.tar.gz

HEALTHCHECK CMD /usr/local/bin/docker-healthcheck.sh || exit 1
