FROM node:16.6.2-alpine3.14 as builder
USER root
RUN apk --no-cache add \
    alpine-sdk \
    jq \
    linux-headers \
    python3

USER node
WORKDIR /home/node
RUN git clone -b v8.0.8 --depth 1 https://github.com/zwave-js/node-zwave-js
RUN git clone -b v5.4.5 --depth 1 https://github.com/zwave-js/zwavejs2mqtt

WORKDIR /home/node/node-zwave-js
COPY zwave-js-sentry.patch .
RUN git apply zwave-js-sentry.patch
RUN yarn install --immutable
RUN yarn lerna run build
RUN sed -i '/yarnPath/d' .yarnrc.yml
RUN for i in config core serial shared; do \
    cd packages/$i && \
    yarn version --no-git-tag-version --new-version \
    $(yarn versions --json | jq -r '[.data."@zwave-js/'${i}'"]'[0])+$(git rev-parse --short HEAD) && \
    yarn link && \cd ../..; \
    done
RUN cd packages/zwave-js && \
    yarn version --no-git-tag-version --new-version \
    $(yarn versions --json | jq -r '[.data."zwave-js"]'[0])+$(git rev-parse --short HEAD) && \
    yarn link

WORKDIR /home/node/zwavejs2mqtt
COPY zwavejs2mqtt-sentry.patch .
RUN git apply zwavejs2mqtt-sentry.patch
RUN yarn install --immutable
RUN yarn run build
RUN yarn link zwave-js @zwave-js/core @zwave-js/config @zwave-js/serial @zwave-js/shared

WORKDIR /home/node
RUN mkdir dist && cp -Lr \
    zwavejs2mqtt/bin \
    zwavejs2mqtt/config \
    zwavejs2mqtt/dist \
    zwavejs2mqtt/hass \
    zwavejs2mqtt/lib \
    zwavejs2mqtt/node_modules \
    zwavejs2mqtt/package.json \
    zwavejs2mqtt/server \
    zwavejs2mqtt/store \
    zwavejs2mqtt/views \
    zwavejs2mqtt/yarn.lock \
    dist

FROM node:16.6.2-alpine3.14
ENV ZWAVEJS_EXTERNAL_CONFIG=/usr/src/app/store/.config-db
COPY --from=builder /home/node/dist /usr/src/app
WORKDIR /usr/src/app
EXPOSE 8091
CMD ["node", "server/bin/www"]
