FROM arm64v8/ubuntu:xenial

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

RUN mkdir /cuda-libs
WORKDIR /cuda-libs

ARG L4T_URL=http://developer.nvidia.com/embedded/dlc/l4t-jetson-tx2-driver-package-28-2
ARG JETPACK_URL=http://developer.download.nvidia.com/devzone/devcenter/mobile/jetpack_l4t/3.2/pwv346/JetPackL4T_32_b157

RUN  apt-get update \
  && apt-get install -y --no-install-recommends bzip2 \
                                                ca-certificates \
                                                curl \
  # run the tegra library installation
  && curl -sL $L4T_URL | tar xfj - \
  && sed -ie 's/sudo //g' ./Linux_for_Tegra/apply_binaries.sh \
  && ./Linux_for_Tegra/apply_binaries.sh -r / \
  # Pull the rest of the jetpack libs for cuda/cudnn and install
  && curl $JETPACK_URL/cuda-repo-l4t-9-0-local_9.0.252-1_arm64.deb -so cuda-repo-l4t-9-0-local.deb \
  && curl $JETPACK_URL/libcudnn7_7.0.5.13-1+cuda9.0_arm64.deb -so libcudnn7.deb \
  && curl $JETPACK_URL/libcudnn7-dev_7.0.5.13-1+cuda9.0_arm64.deb -so libcudnn7-dev.deb \
  && dpkg -i cuda-repo-l4t-9-0-local.deb \
  && dpkg -i libcudnn7.deb \
  && dpkg -i libcudnn7-dev.deb \
  && apt-key add /var/cuda-repo-9-0-local/7fa2af80.pub \
  && apt-get update \
  && apt-get install -y --no-install-recommends cuda-core-9-0 \
                                                cuda-command-line-tools-9-0 \
                                                cuda-libraries-dev-9-0 \
                                                cuda-nvml-dev-9-0 \
  && apt-get remove -y cuda-repo-l4t-9-0-local \
  && rm /etc/apt/sources.list.d/cuda-9-0-local.list \
  && apt-get remove -y --autoremove ca-certificates curl \
  && apt-get autoclean -y \
  && rm -rf /var/cache/apt /var/lib/apt/lists/* \
  && rm -rf /cuda-libs

WORKDIR /

# Re-link libs
RUN  ln -s libnvidia-ptxjitcompiler.so.28.2.0 /usr/lib/aarch64-linux-gnu/tegra/libnvidia-ptxjitcompiler.so.1 \
  && ln -s libcuda.so.1.1 /usr/lib/aarch64-linux-gnu/tegra/libcuda.so.1 \
  && ln -s cuda-9.0 /usr/local/cuda

# perform alternatives updates to use tegra over mesa
RUN  echo /usr/lib/aarch64-linux-gnu/tegra > /usr/lib/aarch64-linux-gnu/tegra/ld.so.conf \
  && update-alternatives --install /etc/ld.so.conf.d/aarch64-linux-gnu_GL.conf aarch64-linux-gnu_gl_conf /usr/lib/aarch64-linux-gnu/tegra/ld.so.conf 1000 \
  && echo /usr/lib/aarch64-linux-gnu/tegra-egl > /usr/lib/aarch64-linux-gnu/tegra-egl/ld.so.conf \
  && update-alternatives --install /etc/ld.so.conf.d/aarch64-linux-gnu_EGL.conf aarch64-linux-gnu_egl_conf /usr/lib/aarch64-linux-gnu/tegra-egl/ld.so.conf 1000 \
  && rm /etc/ld.so.conf.d/nvidia-tegra.conf \
  && ldconfig
