ARG BASE
FROM ${BASE}
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

ENTRYPOINT ["/entrypoint.sh"]
WORKDIR /data

RUN apt-get update --fix-missing &&\
    apt install -y --no-install-recommends jq && \
    apt clean -y && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /
