FROM flacjacket/cuda-tx2:3.3-20181207 as pytorch_builder

COPY --from=flacjacket/cmake-tx2:3.13.1-20181207 /cmake.tar.gz /
RUN  tar -xf cmake.tar.gz -C /usr --strip 1

COPY --from=flacjacket/wheels-tx2:3.7-20181207 /wheelhouse/numpy*.whl /

ARG TORCH_CUDA_ARCH_LIST=6.2
ARG TORCH_VERSION=1.0.0

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
  && sed -i -e 's/option(USE_NCCL "Use NCCL" ON)/option(USE_NCCL "Use NCCL" OFF)/g' CMakeLists.txt \
  && sed -i -e 's/USE_NCCL = USE_CUDA and not IS_DARWIN and not IS_WINDOWS/USE_NCCL = False/g' tools/setup_helpers/nccl.py \
  && python3 setup.py build_deps \
  && python3 setup.py bdist_wheel \
  && cp dist/torch*.whl / \
  && rm -rf /pytorch /var/cache/apt /var/lib/apt/lists/*

FROM flacjacket/cuda-tx2:3.3-20181207

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

COPY --from=pytorch_builder /torch-*.whl /
COPY --from=flacjacket/wheels-tx2:3.7-20181207 /wheelhouse/numpy-*.whl /

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
  && pip install /torch-*.whl \
  && apt-get remove --autoremove -y curl \
  && rm -rf /numpy-*.whl /var/cache/apt /var/lib/apt/lists/* get-pip.py
