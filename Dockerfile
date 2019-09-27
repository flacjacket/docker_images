FROM flacjacket/cuda-tx2:4.2.2-20190926 as pytorch_builder

COPY --from=flacjacket/cmake-tx2:3.15.3-20190926 /cmake.tar.gz /
RUN  tar -xf cmake.tar.gz -C /usr --strip 1

COPY --from=flacjacket/wheels-tx2:3.7-20190926 /wheelhouse/numpy*.whl /

RUN  apt-get update \
  && apt-get install -y --no-install-recommends gnupg \
  && echo "deb http://ppa.launchpad.net/deadsnakes/ppa/ubuntu bionic main" >> /etc/apt/sources.list \
  && echo "deb-src http://ppa.launchpad.net/deadsnakes/ppa/ubuntu bionic main" >> /etc/apt/sources.list \
  && while [ 1 ]; do \
     apt-key adv --keyserver pgp.mit.edu \
                 --recv-keys F23C5A6CF475977595C89F51BA6932366A755776 && break || true; \
     done \
  && apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
                                                curl \
                                                git \
                                                python3.7-dev \
  && ln -sf python3.7 /usr/bin/python3 \
  && ln -sf python3.7 /usr/bin/python \
  && curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
  && python3 get-pip.py --no-cache-dir \
  && pip install --no-cache-dir pyyaml \
  && pip install --no-cache-dir /numpy*.whl

ARG TORCH_VERSION=v1.2.0
RUN git clone --recursive -b ${TORCH_VERSION} --depth 1 https://github.com/pytorch/pytorch

WORKDIR /pytorch

ARG TORCH_CUDA_ARCH_LIST=6.2
ARG USE_DISTRIBUTED=0
ARG USE_NCCL=0

RUN  python setup.py bdist_wheel \
  && cp dist/torch*.whl /

FROM flacjacket/cuda-tx2:4.2.2-20190926

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

COPY --from=pytorch_builder /torch-*.whl /
COPY --from=flacjacket/wheels-tx2:3.7-20190926 /wheelhouse/numpy*.whl /

RUN  apt-get update \
  && apt-get install -y --no-install-recommends gnupg \
  && echo "deb http://ppa.launchpad.net/deadsnakes/ppa/ubuntu bionic main" >> /etc/apt/sources.list \
  && echo "deb-src http://ppa.launchpad.net/deadsnakes/ppa/ubuntu bionic main" >> /etc/apt/sources.list \
  && while [ 1 ]; do \
     apt-key adv --keyserver pgp.mit.edu \
                 --recv-keys F23C5A6CF475977595C89F51BA6932366A755776 && break || true; \
     done \
  && apt-get update \
  && apt-get install -y --no-install-recommends python3.7 \
                                                curl \
  && ln -sf python3.7 /usr/bin/python3 \
  && ln -sf python3.7 /usr/bin/python \
  && curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
  && python get-pip.py --no-cache-dir \
  && pip install /numpy-*.whl \
  && pip install /torch-*.whl \
  && apt-get remove --autoremove -y curl gnupg \
  && rm -rf /numpy-*.whl /var/cache/apt /var/lib/apt/lists/* get-pip.py
