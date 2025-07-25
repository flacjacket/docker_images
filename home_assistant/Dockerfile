FROM homeassistant/home-assistant:2025.7.3

COPY docker-healthcheck.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-healthcheck.sh

COPY *.patch /
RUN  cd /usr/src/homeassistant/ \
  && git apply /00_no_cloud.patch \
  && git apply /01_venstar.patch \
  && rm /*.patch

RUN addgroup -g 1000 home_assistant \
 && adduser -D -u 1000 -h /config -G home_assistant home_assistant \
 && adduser home_assistant audio \
 && chown 1000:1000 -R /usr/local/lib/python3*/site-packages /usr/local/bin /tmp /tmp/* \
 && chmod +x /etc/services.d/home-assistant/run \
 && chmod +x /etc/services.d/home-assistant/finish

RUN mkdir -p /static_config/custom_components/hacs && \
    wget "https://github.com/hacs/integration/releases/latest/download/hacs.zip" && \
    unzip hacs.zip -d /static_config/custom_components/hacs && \
    rm -r hacs.zip
COPY *.yaml /static_config/
COPY automations /static_config/automations
COPY blueprints /static_config/blueprints
COPY scripts /static_config/scripts
RUN chmod 444 /static_config/*.yaml

HEALTHCHECK CMD /usr/local/bin/docker-healthcheck.sh || exit 1
