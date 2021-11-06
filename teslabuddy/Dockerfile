FROM python

WORKDIR /app

RUN useradd -m user
USER user

RUN pip install --user paho-mqtt
COPY teslabuddy.py /app/

CMD ["python", "/app/teslabuddy.py", "/app/secrets.json"]
