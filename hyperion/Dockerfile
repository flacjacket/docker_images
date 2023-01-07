FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      gnupg2 \
      lsb-release \
      wget && \
    rm -rf /var/lib/apt/lists/*

RUN wget -qO- https://apt.hyperion-project.org/hyperion.pub.key | gpg --dearmor -o /usr/share/keyrings/hyperion.pub.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/hyperion.pub.gpg] https://apt.hyperion-project.org/ $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hyperion.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends hyperion && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir /hyperion

CMD ["hyperiond", "-u", "/hyperion"]

