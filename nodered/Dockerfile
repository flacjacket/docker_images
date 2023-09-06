FROM nodered/node-red:3.1.0-14 as builder

LABEL description="Build container for node red with home assistant nodes" \
      maintainer="sean.v.775@gmail.com"


# Add packages needed to build native dependencies
USER root
RUN apk add --no-cache \
    git \
    python3-dev \
    py3-pip \
    py3-virtualenv \
    build-base \
    libc6-compat

WORKDIR /usr/src/node-red/

RUN  npm install node-red-contrib-home-assistant-websocket@0.43.1 \
  && npm install node-red-contrib-bigtimer@2.8.1

FROM nodered/node-red:3.1.0-14

LABEL description="Node red container with home assistant nodes" \
      maintainer="sean.v.775@gmail.com"

COPY --from=builder /usr/src/node-red/node_modules /usr/src/node-red/node_modules
