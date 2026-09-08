ARG BASE_REGISTRY=docker.io
FROM ${BASE_REGISTRY}/library/ubuntu:26.04@sha256:da6fc2be547864451aa253836dd926da33623312df4a9a243e35dc877c378a78
ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture i386 && apt-get update && apt-get install -y --no-install-recommends python3 python3-venv python3-pip xvfb openbox x11vnc novnc x11-utils xdotool mesa-utils vulkan-tools libgl1-mesa-dri libgl1 libgl1:i386 libgl1-mesa-dri:i386 libasound2t64 libasound2t64:i386 libstdc++6:i386 libx11-6:i386 libxcursor1:i386 libxext6:i386 libxi6:i386 libxinerama1:i386 libxrandr2:i386 libxss1:i386 libxtst6:i386 libudev1:i386 libopenal1 dbus-x11 curl ca-certificates zbar-tools fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
ARG HOST_UID=1000
ARG HOST_GID=1000
RUN usermod -l researcher ubuntu && groupmod -n researcher ubuntu && groupmod -o -g ${HOST_GID} researcher && usermod -u ${HOST_UID} -g ${HOST_GID} -d /state/home researcher && chmod 0666 /etc/passwd /etc/group
WORKDIR /opt/gamecua
COPY requirements.lock.txt pyproject.toml ./
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.lock.txt aiohttp==3.13.3 qrcode==8.2
RUN sed -i 's|http://|https://|g' /etc/apt/sources.list.d/ubuntu.sources && apt-get -o Acquire::https::Timeout=30 -o Acquire::Retries=3 update && apt-get -o Acquire::https::Timeout=30 -o Acquire::Retries=3 install -y --no-install-recommends libvorbisfile3 libsnappy1v5 libglu1-mesa libglib2.0-0t64:i386 libgtk2.0-0t64:i386 libpipewire-0.3-0t64:i386 libpulse0:i386 libgdk-pixbuf-2.0-0:i386 libxcb-res0:i386 libva2:i386 libvdpau1:i386 libbz2-1.0:i386 libopenal1:i386 libsm6:i386 libice6:i386 libcurl4t64:i386 && rm -rf /var/lib/apt/lists/*
RUN --mount=type=bind,source=build-cache,target=/build-cache (cp /build-cache/virtualgl_3.1.5_amd64.deb /tmp/virtualgl.deb || curl -fsSL --retry 5 --retry-all-errors https://github.com/VirtualGL/virtualgl/releases/download/3.1.5/virtualgl_3.1.5_amd64.deb -o /tmp/virtualgl.deb) && echo "df3f7788ce41b182a47c0d298e5cd6d2d63579522cb41825970b7726e825485e  /tmp/virtualgl.deb" | sha256sum -c - && dpkg -i /tmp/virtualgl.deb && rm /tmp/virtualgl.deb
RUN apt-get update && apt-get install -y --no-install-recommends lsof && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y --no-install-recommends xz-utils x11-xserver-utils libnm0 libnm0:i386 libpipewire-0.3-0t64 libsdl2-2.0-0 libsdl2-2.0-0:i386 && rm -rf /var/lib/apt/lists/*
COPY gamecua ./gamecua
COPY benchmarks ./benchmarks
RUN /opt/venv/bin/pip install --no-deps .
ENV GAMECUA_GRAPHICS_PRESET=software PYTHONPATH=/opt/gamecua PATH=/opt/venv/bin:$PATH DISPLAY=:99 HOME=/state/home XDG_RUNTIME_DIR=/state/runtime GDK_BACKEND=x11 SDL_VIDEODRIVER=x11
LABEL org.opencontainers.image.source="https://github.com/Touchstone-AI-Lab/GameCUA"
LABEL org.opencontainers.image.version="0.7.14"
USER researcher
ENTRYPOINT ["python", "-m", "gamecua.environments.session"]
