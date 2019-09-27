FROM arm64v8/ubuntu:bionic-20190912.1

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

ARG DEBIAN_FRONTEND=noninteractive

ARG PIP_OPTS="--no-cache-dir"
ARG WHEEL_OPTS="-w /wheelhouse"
ARG NUMPY_OPTS="--global-option build_ext --global-option -j7"

RUN  apt-get update \
  && apt-get install -y --no-install-recommends gnupg \
  && echo "deb http://ppa.launchpad.net/deadsnakes/ppa/ubuntu bionic main" >> /etc/apt/sources.list \
  && echo "deb-src http://ppa.launchpad.net/deadsnakes/ppa/ubuntu bionic main" >> /etc/apt/sources.list \
  && apt-key adv --keyserver pgp.mit.edu --recv-keys F23C5A6CF475977595C89F51BA6932366A755776 \
  && apt-get update \
  && export build_deps=' \
       build-essential \
       ca-certificates \
       curl \
       gnupg \
       libffi-dev \
       python3.7-dev \
     ' \
  && apt-get install -y --no-install-recommends $build_deps \
  && ln -s python3.7 /usr/bin/python \
  && curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
  && python get-pip.py $PIP_OPTS \
  && pip wheel $WHEEL_OPTS $PIP_OPTS cffi==1.12.3 \
                                     grpcio==1.24.0 \
  && pip wheel $WHEEL_OPTS $PIP_OPTS $NUMPY_OPTS numpy==1.17.2 \
  && apt-get remove -y --autoremove $build_deps \
  && rm /wheelhouse/six* /wheelhouse/pycparser* \
  && rm -rf /usr/local/lib /usr/local/bin /var/cache/apt /var/lib/apt/lists/* get-pip.py
