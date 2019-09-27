FROM arm64v8/ubuntu:bionic-20190912.1

LABEL maintainer="Sean Vig <sean.v.775@gmail.com>"

RUN mkdir /cuda-libs
WORKDIR /cuda-libs

ARG TEGRA_BASE_URL=https://developer.nvidia.com/embedded/dlc/r32-2-1_Release_v1.0/TX2-AGX/
ARG TEGRA_FILE=Tegra186_Linux_R32.2.1_aarch64.tbz2

ARG CUDA_BASE_URL=https://developer.download.nvidia.com/devzone/devcenter/mobile/jetpack_l4t/JETPACK_422_b21
ARG CUDA_URL_EXT=/P3310
ARG CUDA_REPO_FILE=cuda-repo-l4t-10-0-local-10.0.326_1.0-1_arm64.deb
ARG CUDNN_FILE=libcudnn7_7.5.0.56-1+cuda10.0_arm64.deb
ARG CUDNN_DEV_FILE=libcudnn7-dev_7.5.0.56-1+cuda10.0_arm64.deb

COPY apply_binaries.patch .
COPY manifest.sha512 .

RUN  apt-get update \
  && apt-get install -y --no-install-recommends bzip2 \
                                                ca-certificates \
                                                gnupg2 \
                                                patch \
                                                lbzip2 \
                                                wget \
  && wget --progress=bar:force:noscroll $TEGRA_BASE_URL/$TEGRA_FILE \
                                        $CUDA_BASE_URL/$CUDA_REPO_FILE \
                                        $CUDA_BASE_URL/$CUDA_URL_EXT/$CUDNN_FILE \
                                        $CUDA_BASE_URL/$CUDA_URL_EXT/$CUDNN_DEV_FILE \
  && sha512sum -c manifest.sha512 \
  # run the tegra library installation
  && tar -xjf $TEGRA_FILE \
  && patch -p0 < apply_binaries.patch \
  && ./Linux_for_Tegra/apply_binaries.sh -r / \
  # install the rest of the jetpack libs for cuda/cudnn
  && dpkg -i $CUDA_REPO_FILE \
  && dpkg -i $CUDNN_FILE \
  && dpkg -i $CUDNN_DEV_FILE \
  && apt-key add /var/cuda-repo-*/*.pub \
  && apt-get remove -y --autoremove ca-certificates gnupg2 lbzip2 patch wget \
  && apt-get update \
  && apt-get install -y --no-install-recommends cuda-compiler-10-0 \
                                                cuda-command-line-tools-10-0 \
                                                cuda-libraries-dev-10-0 \
                                                cuda-nvml-dev-10-0 \
  && apt-get remove -y cuda-repo-l4t-10-0-local-10.0.326 \
  && rm /etc/apt/sources.list.d/cuda-10-0-local-10.0.326.list \
  && apt-get autoclean -y \
  && rm -rf /var/cache/apt /var/lib/apt/lists/* \
  && rm -rf /cuda-libs

WORKDIR /

# Re-link libs
RUN  ln -s libnvidia-ptxjitcompiler.so.32.2.1 /usr/lib/aarch64-linux-gnu/tegra/libnvidia-ptxjitcompiler.so.1 \
  && ln -s libcuda.so.1.1 /usr/lib/aarch64-linux-gnu/tegra/libcuda.so.1 \
  && ln -s cuda-10.0 /usr/local/cuda

# perform alternatives updates to use tegra over mesa
RUN  echo /usr/lib/aarch64-linux-gnu/tegra > /usr/lib/aarch64-linux-gnu/tegra/ld.so.conf \
  && update-alternatives --install /etc/ld.so.conf.d/aarch64-linux-gnu_GL.conf aarch64-linux-gnu_gl_conf /usr/lib/aarch64-linux-gnu/tegra/ld.so.conf 1000 \
  && echo /usr/lib/aarch64-linux-gnu/tegra-egl > /usr/lib/aarch64-linux-gnu/tegra-egl/ld.so.conf \
  && update-alternatives --install /etc/ld.so.conf.d/aarch64-linux-gnu_EGL.conf aarch64-linux-gnu_egl_conf /usr/lib/aarch64-linux-gnu/tegra-egl/ld.so.conf 1000 \
  && rm /etc/ld.so.conf.d/nvidia-tegra.conf \
  && ldconfig
