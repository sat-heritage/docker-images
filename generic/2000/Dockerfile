ARG BASE
ARG BUILDER_BASE
FROM ${BUILDER_BASE} as builder

RUN apt-get update --fix-missing && \
    apt-get -y install gcc make libc6-dev

WORKDIR /src

ARG solver
ARG download_url

ADD $download_url /src

COPY $solver.build.sh /src/build.sh

RUN mkdir /dist && bash build.sh
