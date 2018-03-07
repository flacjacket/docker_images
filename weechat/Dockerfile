FROM debian:buster-slim

LABEL description="Container for starting weechat" \
      maintainer="sean.v.775@gmail.com"

ENV TZ=America/New_York \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

RUN apt-get update \
    && echo $TZ > /etc/timezone \
    && apt-get install -y --no-install-recommends tzdata locales \
    && echo en_US.UTF-8 UTF-8 >> /etc/locale.gen \
    && locale-gen \
    && update-locale LC_ALL=${LC_ALL} LANG=${LANG}

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
                                                  dirmngr \
                                                  gnupg \
    && echo "deb https://weechat.org/debian buster main" > /etc/apt/sources.list.d/weechat.list \
    && apt-key adv --keyserver ipv4.pool.sks-keyservers.net --recv-keys 11E9DE8848F2B65222AA75B8D1820DB22A11534E \
    && apt-get update \
    && apt-get install -y --no-install-recommends openssh-server \
                                                  tmux \
                                                  weechat-curses \
                                                  weechat-plugins \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/* \
    && rm -rf /var/lib/apt/lists/*

# Configure ssh
RUN mkdir /var/run/sshd \
    && chmod 700 /var/run
ADD sshd_config /etc/ssh/

ENV WEECHAT_GID=1000 \
    WEECHAT_UID=1000

RUN groupadd -r weechat -g $WEECHAT_GID \
    && useradd -m -u $WEECHAT_UID -g $WEECHAT_GID -s /home/weechat/login.sh weechat \
    && mkdir /home/weechat/.ssh \
    && chown $WEECHAT_UID:$WEECHAT_GID /home/weechat/.ssh \
    && chmod 700 /home/weechat/.ssh

ADD login.sh /home/weechat/

VOLUME /home/weechat/.weechat/
VOLUME /home/weechat/.tmux.conf
VOLUME /home/weechat/.ssh/authorized_keys

EXPOSE 22

CMD ["/usr/sbin/sshd", "-D"]
