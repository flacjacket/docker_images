FROM arm64v8/ubuntu:xenial

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

ARG DEBIAN_FRONTEND=noninteractive

RUN  apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
                                                ca-certificates \
                                                python3-dev \
                                                python3-pip \
  && pip3 install --upgrade pip \
  && apt-get remove -y --autoremove python3-pip \
  && pip install setuptools wheel \
  && pip wheel -w /wheelhouse grpcio \
                              wheel \
  && pip wheel -w /wheelhouse --global-option build_ext --global-option -j7 numpy \
  && rm -rf /var/cache/apt /var/lib/apt/lists/*
