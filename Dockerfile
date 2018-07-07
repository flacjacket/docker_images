FROM arm64v8/ubuntu:xenial as bazel_builder

ARG DEBIAN_FRONTEND=noninteractive

RUN mkdir /bazel
WORKDIR /bazel

ARG BAZEL_VERSION=0.13.0
RUN  echo "deb http://ppa.launchpad.net/webupd8team/java/ubuntu xenial main" > /etc/apt/sources.list.d/webupd8team.list \
  && apt-key adv --keyserver ipv4.pool.sks-keyservers.net --recv-keys C2518248EEA14886 \
  && apt-get update \
  && echo "debconf shared/accepted-oracle-license-v1-1 select true" | /usr/bin/debconf-set-selections \
  && apt-get install -y --no-install-recommends oracle-java8-installer \
                                                build-essential \
                                                ca-certificates \
                                                python \
                                                unzip \
                                                zip \
  && wget https://github.com/bazelbuild/bazel/releases/download/${BAZEL_VERSION}/bazel-${BAZEL_VERSION}-dist.zip \
  && unzip bazel-${BAZEL_VERSION}-dist.zip \
  && rm bazel-${BAZEL_VERSION}-dist.zip \
  && ./compile.sh \
  && cp output/bazel /usr/bin/bazel \
  && rm -rf /bazel ~/.cache/bazel \
  && rm -rf /var/cache/apt /var/lib/apt/lists/*

FROM flacjacket/cuda-tx2:3.2 as tf_builder

ARG DEBIAN_FRONTEND=noninteractive

ARG PYTHON_BIN_PATH=/usr/bin/python3
ARG PYTHON_LIB_PATH=/usr/lib/python3/dist-packages
ARG GCC_HOST_COMPILER_PATH=/usr/bin/gcc
ARG CC_OPT_FLAGS=-march=native
ARG CUDA_TOOLKIT_PATH=/usr/local/cuda
ARG CUDNN_INSTALL_PATH=/usr/lib/aarch64-linux-gnu/tegra
ARG TF_CUDA_COMPUTE_CAPABILITIES=6.2
ARG TF_CUDA_CLANG=0
ARG TF_CUDA_VERSION=9.0
ARG TF_CUDNN_VERSION=7.0
ARG TF_ENABLE_XLA=0
ARG TF_NCCL_VERSION=1.3
ARG TF_NEED_CUDA=1
ARG TF_NEED_GCP=0
ARG TF_NEED_GDR=0
ARG TF_NEED_HDFS=0
ARG TF_NEED_JEMALLOC=0
ARG TF_NEED_KAFKA=0
ARG TF_NEED_OPENCL_SYCL=0
ARG TF_NEED_MPI=0
ARG TF_NEED_S3=0
ARG TF_NEED_TENSORRT=0
ARG TF_NEED_VERBS=0
ARG TF_SET_ANDROID_WORKSPACE=0

COPY --from=bazel_builder /usr/bin/bazel /usr/bin/

RUN mkdir /tensorflow_build
WORKDIR /tensorflow_build
COPY png_build.patch .

ARG TENSORFLOW_VERSION=1.8.0
RUN  echo "deb http://ppa.launchpad.net/webupd8team/java/ubuntu xenial main" > /etc/apt/sources.list.d/webupd8team.list \
  && apt-key adv --keyserver ipv4.pool.sks-keyservers.net --recv-keys C2518248EEA14886 \
  && apt-get update \
  && echo "debconf shared/accepted-oracle-license-v1-1 select true" | /usr/bin/debconf-set-selections \
  && build_deps=' \
      oracle-java8-installer \
      build-essential \
      ca-certificates \
      curl \
      python \
      python3-dev \
      python3-numpy \
      python3-pip \
      python3-setuptools \
      python3-wheel \
  ' \
  && apt-get install -y --no-install-recommends $build_deps \
  && curl -SL https://github.com/tensorflow/tensorflow/archive/v${TENSORFLOW_VERSION}.tar.gz | tar -xzC . --strip 1 \
  && patch -p1 -u < png_build.patch \
  && ./configure \
  && for lib in libcuda.so.1 \
                libnvidia-fatbinaryloader.so.28.2.0 \
                libnvos.so \
                libnvrm.so \
                libnvrm_gpu.so; do \
     ln -s tegra/$lib /usr/lib/aarch64-linux-gnu/$lib; \
     done \
  && bazel build --config=opt --config=cuda //tensorflow/tools/pip_package:build_pip_package \
  && bazel-bin/tensorflow/tools/pip_package/build_pip_package /tensorflow/ \
  && pip3 install /tensorflow/*.whl --user \
  && cp ~/.cache/pip/wheels/*/*/*/*/*.whl /tensorflow \
  && apt-get purge -y --auto-remove $build_deps \
  && rm -r ~/.cache ~/.local /tensorflow_build \
  && rm -rf /var/cache/apt /var/lib/apt/lists/*
