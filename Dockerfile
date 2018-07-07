FROM arm64v8/ubuntu:xenial-20180525 as cmake_builder

ARG CMAKE_VERSION=3.11.4

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

FROM flacjacket/cuda-tx2:3.2.1-20180707 as opencv_builder

ARG CMAKE_VERSION=3.11.4

COPY --from=cmake_builder /cmake-${CMAKE_VERSION}.tar.gz /
RUN  tar -xf cmake-${CMAKE_VERSION}.tar.gz -C /usr --strip 1

RUN mkdir /opencv
WORKDIR /opencv

RUN  apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
                                                curl \
                                                python3-dev \
                                                python3-numpy \
                                                libpng12-dev \
                                                libjpeg8-dev \
                                                libjasper-dev \
                                                libtiff5-dev \
                                                libgstreamer1.0-dev \
                                                libgstreamer-plugins-base1.0-dev \
                                                gstreamer1.0-plugins-base \
  && curl -LS https://github.com/opencv/opencv/archive/3.4.1.tar.gz | tar -xzC . --strip 1 \
  && mkdir build \
  && cd build \
  && cmake -D CMAKE_BUILD_TYPE=RELEASE \
           -D CMAKE_INSTALL_PREFIX=/usr \
           -D WITH_CUDA=ON \
           -D WITH_CUBLAS=ON \
           -D WITH_CUFFT=ON \
           -D CUDA_ARCH_BIN="6.2" \
           -D CUDA_ARCH_PTX="" \
           -D ENABLE_FAST_MATH=ON \
           -D CUDA_FAST_MATH=ON \
           -D ENABLE_NEON=ON \
           -D WITH_LIBV4L=ON \
           -D BUILD_TESTS=OFF \
           -D BUILD_PERF_TESTS=OFF \
           -D BUILD_EXAMPLES=OFF \
           -D WITH_QT=OFF \
           -D WITH_OPENGL=ON \
           -D WITH_FFMPEG=ON \
           -D WITH_V4L=ON \
           -D WITH_LIBV4L=ON \
           -D WITH_LAPACK=ON \
           -D WITH_OPENGL=ON \
           .. \
  && make -j7 \
  && make package \
  && cp /opencv/build/OpenCV-unknown-aarch64.tar.gz /OpenCV-3.4.1.tar.gz

FROM flacjacket/cuda-tx2:3.2.1-20180707

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

COPY --from=opencv_builder /OpenCV-3.4.1.tar.gz /
COPY --from=flacjacket/wheels-tx2:20180707 /wheelhouse/numpy*.whl /

RUN  tar -xf /OpenCV-3.4.1.tar.gz -C /usr --strip 1 \
  && apt-get update \
  && apt-get install -y --no-install-recommends gstreamer1.0-plugins-base \
                                                libgstreamer1.0-0 \
                                                libjasper1 \
                                                libjpeg8 \
                                                libpng12-0 \
                                                libtiff5 \
                                                python3 \
                                                python3-pip \
  && pip3 install --no-cache-dir /numpy*.whl \
  && apt-get remove -y --autoremove python3-pip \
  && rm /OpenCV-3.4.1.tar.gz \
  && rm /numpy*.whl \
  && rm -rf /var/cache/apt /var/lib/apt/lists/*
