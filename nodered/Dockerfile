FROM nodered/node-red-docker:0.18.4-slim-v8 as builder

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

RUN npm install node-red-contrib-home-assistant@0.3.0

FROM nodered/node-red-docker:0.18.4-slim-v8

LABEL description="Node red container with home assistant nodes" \
      maintainer="sean.v.775@gmail.com"

COPY --from=builder /usr/src/node-red/node_modules ./node_modules
