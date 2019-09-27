FROM arm64v8/ubuntu:bionic-20190912.1

ARG CMAKE_VERSION=3.15.3

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
