FROM golang:1.18

WORKDIR /go/src/app
RUN apt-get update && \
    apt-get install -y --no-install-recommends unzip && \
    rm -rf /var/lib/apt/lists/*
RUN wget https://github.com/deepch/RTSPtoWebRTC/archive/refs/heads/master.zip && \
    unzip master.zip

WORKDIR /go/src/app/RTSPtoWebRTC-master
ENV GIN_MODE=release
RUN go install

EXPOSE 8083

ENTRYPOINT ["RTSPtoWebRTC"]
CMD []
