FROM nvcr.io/nvidia/l4t-base:r32.5.0

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

RUN  apt-get update \
  && apt-get install -y --no-install-recommends \
         ca-certificates \
  && rm -rf /var/cache/apt /var/lib/apt/lists/*

COPY jetson-ota-public.asc /etc/apt/trusted.gpg.d/jetson-ota-public.asc
RUN  echo "deb https://repo.download.nvidia.com/jetson/common r32.5 main" >> /etc/apt/sources.list.d/nvidia-l4t-apt-source.list \
  && echo "deb https://repo.download.nvidia.com/jetson/t186 r32.5 main" >> /etc/apt/sources.list.d/nvidia-l4t-apt-source.list \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
         cuda-libraries-10-2 \
         cuda-nvrtc-10-2 \
         cuda-nvtx-10-2 \
         python3-libnvinfer \
  && ln -sf python3 /usr/bin/python \
  && rm -rf /var/cache/apt /var/lib/apt/lists/*
