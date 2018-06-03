FROM arm64v8/ubuntu:xenial as cmake_builder

ARG CMAKE_VERSION=3.11.2

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
  && rm -rf /cmake /var/cache/apt /var/lib/apt/lists/*

FROM flacjacket/cuda-tx2:3.2 as pytorch_builder

ARG CMAKE_VER=3.11.2
ARG TORCH_CUDA_ARCH_LIST=6.2
ARG TORCH_VERSION=0.4.0

COPY --from=cmake_builder /cmake-${CMAKE_VER}.tar.gz /
RUN tar -xf cmake-${CMAKE_VER}.tar.gz -C /usr --strip 1

RUN  apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
                                                git \
                                                python3-dev \
                                                python3-numpy \
                                                python3-setuptools \
                                                python3-wheel \
                                                python3-yaml \
  && git clone --recursive -b v${TORCH_VERSION} --depth 1 https://github.com/pytorch/pytorch \
  && ln -s tegra-egl/libEGL.so.1 /usr/lib/aarch64-linux-gnu/libEGL.so.1 \
  && ln -s tegra-egl/libGLESv2.so.2 /usr/lib/aarch64-linux-gnu/libGLESv2.so.2 \
  && cd pytorch \
  && python3 setup.py build_deps \
  && python3 setup.py bdist_wheel \
  && cp dist/torch-${TORCH_VERSION}*-cp35-cp35m-linux_aarch64.whl /torch-${TORCH_VERSION}-cp35-cp35m-linux_aarch64.whl \
  && rm -rf /pytorch /var/cache/apt /var/lib/apt/lists/*

FROM flacjacket/cuda-tx2:3.2

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

ARG TORCH_VERSION=0.4.0

COPY --from=pytorch_builder /torch-${TORCH_VERSION}-cp35-cp35m-linux_aarch64.whl /
COPY --from=flacjacket/wheels-tx2:20180602 /wheelhouse/numpy-1.14.3-cp35-cp35m-linux_aarch64.whl /
COPY --from=flacjacket/wheels-tx2:20180602 /wheelhouse/wheel-0.31.1-py2.py3-none-any.whl /

RUN  apt-get update \
  && apt-get install -y --no-install-recommends python3-pip \
  && pip3 install /numpy-1.14.3-cp35-cp35m-linux_aarch64.whl \
  && pip3 install /torch-${TORCH_VERSION}-cp35-cp35m-linux_aarch64.whl \
  && rm -rf /var/cache/apt /var/lib/apt/lists/*
