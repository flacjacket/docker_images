FROM arm64v8/ubuntu:xenial-20180726 as cmake_builder

ARG CMAKE_VERSION=3.12.0

RUN mkdir /cmake
WORKDIR /cmake

RUN  apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
                                                ca-certificates \
                                                curl \
  && SHORT_VERSION=`expr match "$CMAKE_VERSION" '\([0-9]*\.[0-9]*\)'` \
  && curl -LS https://cmake.org/files/v${SHORT_VERSION}/cmake-${CMAKE_VERSION}.tar.gz | tar -xzC . --strip 1 \
  && ./bootstrap --parallel=7 \
  && make -j7 \
  && make package \
  && cp /cmake/cmake-${CMAKE_VERSION}-Linux-aarch64.tar.gz /cmake-${CMAKE_VERSION}.tar.gz \
  && mv /cmake-${CMAKE_VERSION}.tar.gz /cmake.tar.gz \
  && rm -rf /cmake /var/cache/apt /var/lib/apt/lists/*

FROM flacjacket/cuda-tx2:3.3-20180802 as pytorch_builder

COPY --from=cmake_builder /cmake.tar.gz /
RUN  tar -xf cmake.tar.gz -C /usr --strip 1

COPY --from=flacjacket/wheels-tx2:3.7-20180802 /wheelhouse/numpy*.whl /

ARG TORCH_CUDA_ARCH_LIST=6.2
ARG TORCH_VERSION=0.4.1

RUN  echo "deb http://ppa.launchpad.net/deadsnakes/ppa/ubuntu xenial main" >> /etc/apt/sources.list \
  && echo "deb-src http://ppa.launchpad.net/deadsnakes/ppa/ubuntu xenial main" >> /etc/apt/sources.list \
  && apt-key adv --keyserver pgp.mit.edu --recv-keys F23C5A6CF475977595C89F51BA6932366A755776 \
  && apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
                                                curl \
                                                git \
                                                python3.7-dev \
  && ln -s python3.7 /usr/bin/python3 \
  && ln -sf python3.7 /usr/bin/python \
  && curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
  && python3 get-pip.py --no-cache-dir \
  && pip install --no-cache-dir pyyaml \
  && pip install --no-cache-dir /numpy*.whl \
  && git clone --recursive -b v${TORCH_VERSION} --depth 1 https://github.com/pytorch/pytorch \
  && ln -s tegra-egl/libEGL.so.1 /usr/lib/aarch64-linux-gnu/libEGL.so.1 \
  && ln -s tegra-egl/libGLESv2.so.2 /usr/lib/aarch64-linux-gnu/libGLESv2.so.2 \
  && cd pytorch \
  && python3 setup.py build_deps \
  && python3 setup.py bdist_wheel \
  && cp dist/torch*.whl / \
  && rm -rf /pytorch /var/cache/apt /var/lib/apt/lists/*

FROM flacjacket/cuda-tx2:3.3-20180802

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

ARG TORCH_VERSION=0.4.1

COPY --from=pytorch_builder /torch-${TORCH_VERSION}*.whl /
COPY --from=flacjacket/wheels-tx2:3.7-20180802 /wheelhouse/numpy-*.whl /

RUN  echo "deb http://ppa.launchpad.net/deadsnakes/ppa/ubuntu xenial main" >> /etc/apt/sources.list \
  && echo "deb-src http://ppa.launchpad.net/deadsnakes/ppa/ubuntu xenial main" >> /etc/apt/sources.list \
  && apt-key adv --keyserver pgp.mit.edu --recv-keys F23C5A6CF475977595C89F51BA6932366A755776 \
  && apt-get update \
  && apt-get install -y --no-install-recommends python3.7 \
                                                curl \
  && ln -s python3.7 /usr/bin/python3 \
  && ln -sf python3.7 /usr/bin/python \
  && curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
  && python3 get-pip.py --no-cache-dir \
  && pip install /numpy-*.whl \
  && pip install /torch-${TORCH_VERSION}*.whl \
  && apt-get remove --autoremove -y curl \
  && rm -rf /numpy-*.whl /var/cache/apt /var/lib/apt/lists/* get-pip.py
