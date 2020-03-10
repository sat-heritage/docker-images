ARG BASE
FROM ${BASE}
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

ENTRYPOINT ["/entrypoint.sh"]
WORKDIR /data

COPY timeout /usr/bin/

ADD https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux32 /usr/bin
RUN chmod +x /usr/bin/jq-linux32 && ln -s /usr/bin/jq-linux32 /usr/bin/jq

COPY entrypoint.sh /
