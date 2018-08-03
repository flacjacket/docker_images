FROM arm64v8/ubuntu:xenial-20180726

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

RUN mkdir /cuda-libs
WORKDIR /cuda-libs

ARG JETPACK_URL=https://developer.download.nvidia.com/devzone/devcenter/mobile/jetpack_l4t/3.3/lw.xd42/JetPackL4T_33_b39
ARG TEGRA_FILE=Tegra186_Linux_R28.2.1_aarch64.tbz2
ARG CUDA_REPO_FILE=cuda-repo-l4t-9-0-local_9.0.252-1_arm64.deb
ARG CUDNN_FILE=libcudnn7_7.1.5.14-1+cuda9.0_arm64.deb
ARG CUDNN_DEV_FILE=libcudnn7-dev_7.1.5.14-1+cuda9.0_arm64.deb

COPY manifest.md5 .

RUN  apt-get update \
  && apt-get install -y --no-install-recommends bzip2 \
                                                ca-certificates \
                                                wget \
  && wget --progress=bar:force:noscroll $JETPACK_URL/$TEGRA_FILE \
                                        $JETPACK_URL/$CUDA_REPO_FILE \
                                        $JETPACK_URL/$CUDNN_FILE \
                                        $JETPACK_URL/$CUDNN_DEV_FILE \
  && md5sum -c manifest.md5 \
  # run the tegra library installation
  && tar -xjf $TEGRA_FILE \
  && sed -ie 's/sudo //g' ./Linux_for_Tegra/apply_binaries.sh \
  && ./Linux_for_Tegra/apply_binaries.sh -r / \
  # install the rest of the jetpack libs for cuda/cudnn
  && dpkg -i $CUDA_REPO_FILE \
  && dpkg -i $CUDNN_FILE \
  && dpkg -i $CUDNN_DEV_FILE \
  && apt-key add /var/cuda-repo-9-0-local/*.pub \
  && apt-get update \
  && apt-get install -y --no-install-recommends cuda-core-9-0 \
                                                cuda-command-line-tools-9-0 \
                                                cuda-libraries-dev-9-0 \
                                                cuda-nvml-dev-9-0 \
  && apt-get remove -y cuda-repo-l4t-9-0-local \
  && rm /etc/apt/sources.list.d/cuda-9-0-local.list \
  && apt-get remove -y --autoremove ca-certificates wget \
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
