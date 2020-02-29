ARG BUILDER_BASE
FROM ${BUILDER_BASE} as builder
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN apt-get update --fix-missing &&\
    apt -y install zip gcc g++ cmake make patch xz-utils zlib1g-dev curl

ARG solver
ARG download_url

RUN curl -o $solver.zip -L $download_url \
    && unzip $solver.zip -d /src \
    && rm $solver.zip

COPY setup.json fixtures/$solver* /src/

WORKDIR /src

RUN test -f $solver.pre_build.sh && sh $solver.pre_build.sh || true

RUN cd /src/$solver && sh starexec_build

RUN test -f $solver.post_build.sh && sh $solver.post_build.sh || true

RUN mv /src/$solver/bin /dist
