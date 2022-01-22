FROM python

WORKDIR /app
RUN wget https://raw.githubusercontent.com/merbanan/rtl_433/master/examples/rtl_433_mqtt_hass.py -O rtl_433_mqtt_hass.py

RUN useradd -m user
USER user

RUN pip install --user paho-mqtt

ENTRYPOINT ["python", "-u", "rtl_433_mqtt_hass.py"]
CMD ["-h"]
