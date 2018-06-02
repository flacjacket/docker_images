FROM arm64v8/ubuntu:xenial

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

ARG DEBIAN_FRONTEND=noninteractive
ARG PIP_OPTS="--no-cache-dir"
ARG WHEEL_OPTS="-w /wheelhouse"
ARG NUMPY_OPTS="--global-option build_ext --global-option -j7"

RUN  apt-get update \
  && export build_deps=' \
       build-essential \
       ca-certificates \
       python3-dev \
     ' \
  && apt-get install -y --no-install-recommends python3-pip $build_deps \
  && pip3 install $PIP_OPTS --upgrade pip \
  && apt-get remove -y --autoremove python3-pip \
  && pip install $PIP_OPTS setuptools wheel \
  && pip wheel $WHEEL_OPTS $PIP_OPTS grpcio \
                                     wheel \
  && pip wheel $WHEEL_OPTS $PIP_OPTS $NUMPY_OPTS numpy \
  && apt-get remove -y --autoremove $build_deps \
  && rm -rf /var/cache/apt /var/lib/apt/lists/*
