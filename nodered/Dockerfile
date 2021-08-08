FROM nodered/node-red:2.0.5-12 as builder

LABEL description="Build container for node red with home assistant nodes" \
      maintainer="sean.v.775@gmail.com"


# Add packages needed to build native dependencies
USER root
RUN apk add --no-cache \
    git \
    python \
    python-dev \
    py-pip \
    build-base \
    libc6-compat \
    && pip install virtualenv

WORKDIR /usr/src/node-red/

RUN  npm install node-red-contrib-home-assistant-websocket@0.33.1 \
  && npm install node-red-contrib-bigtimer@2.7.5

FROM nodered/node-red:2.0.5-12

LABEL description="Node red container with home assistant nodes" \
      maintainer="sean.v.775@gmail.com"

COPY --from=builder /usr/src/node-red/node_modules /usr/src/node-red/node_modules
