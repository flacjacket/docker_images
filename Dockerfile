FROM arm64v8/ubuntu:xenial

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

RUN  apt-get update \
  && apt-get install -y --no-install-recommends bzip2 \
                                                ca-certificates \
                                                curl \
  && rm -rf /var/cache/apt /var/lib/apt/lists/*

# Install drivers first
WORKDIR /tmp
ARG L4T_URL=http://developer.nvidia.com/embedded/dlc/l4t-jetson-tx2-driver-package-28-2
RUN  curl -sL $L4T_URL | tar xfj - \
  && sed -ie 's/sudo //g' ./Linux_for_Tegra/apply_binaries.sh \
  && ./Linux_for_Tegra/apply_binaries.sh -r / \
  && rm -rf /tmp/*

# Pull the rest of the jetpack libs for cuda/cudnn and install
WORKDIR /tmp
ARG JETPACK_URL=http://developer.download.nvidia.com/devzone/devcenter/mobile/jetpack_l4t/3.2/pwv346/JetPackL4T_32_b157
RUN  curl $JETPACK_URL/cuda-repo-l4t-9-0-local_9.0.252-1_arm64.deb -so cuda-repo-l4t_arm64.deb \
  && curl $JETPACK_URL/libcudnn7_7.0.5.13-1+cuda9.0_arm64.deb -so libcudnn_arm64.deb \
  && curl $JETPACK_URL/libcudnn7-dev_7.0.5.13-1+cuda9.0_arm64.deb -so libcudnn-dev_arm64.deb \
  && dpkg -i cuda-repo-l4t_arm64.deb \
  && dpkg -i libcudnn_arm64.deb \
  && dpkg -i libcudnn-dev_arm64.deb \
  && apt-key add /var/cuda-repo-9-0-local/7fa2af80.pub \
  && apt-get update \
  && apt-get install -y cuda-toolkit-9.0 \
  && rm -rf /tmp/*

# Re-link libs in /usr/lib/<arch>/tegra
RUN  ln -s libnvidia-ptxjitcompiler.so.28.2.0 /usr/lib/aarch64-linux-gnu/tegra/libnvidia-ptxjitcompiler.so \
  && ln -s libnvidia-ptxjitcompiler.so.28.2.0 /usr/lib/aarch64-linux-gnu/tegra/libnvidia-ptxjitcompiler.so.1 \
  && ln -s libcuda.so.1.1 /usr/lib/aarch64-linux-gnu/tegra/libcuda.so \
  && ln -s libcuda.so.1.1 /usr/lib/aarch64-linux-gnu/tegra/libcuda.so.1 \
  && ln -sf tegra/libGL.so /usr/lib/aarch64-linux-gnu/libGL.so

ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/lib/aarch64-linux-gnu/tegra

## Clean up
RUN  apt-get -y remove ca-certificates curl \
  && apt-get -y autoremove \
  && apt-get -y autoclean \
  && rm -rf /var/cache/apt /var/lib/apt/lists/*

WORKDIR /
