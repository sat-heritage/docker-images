ARG BASE
ARG BUILDER_BASE
FROM ${BUILDER_BASE} as builder
ENV LANG=C LC_ALL=C

RUN apt-get update --fix-missing &&\
    apt-get -y install zip gcc g++ cmake make patch curl zlib1g-dev

ARG BUILD_DEPENDS
RUN if test "${BUILD_DEPENDS}"; then \
    apt-get install -y --no-install-recommends ${BUILD_DEPENDS}; fi

ARG solver
ARG solver_id
ARG download_url

WORKDIR /src

ADD $download_url /src/$solver_id.tgz
RUN tar xzf $solver_id.tgz

COPY setup.json fixtures/$solver_id* /src/

RUN test -f $solver_id.pre_build.sh && sh $solver_id.pre_build.sh || true

RUN mkdir /dist && cd `find -maxdepth 1 -mindepth 1 -type d` && \
    if test -f /src/$solver_id.build.sh; then sh /src/$solver_id.build.sh; else \
    make && find -perm +100 -type f -exec mv -v {} /dist \;; fi

RUN test -f $solver_id.post_build.sh && sh $solver_id.post_build.sh || true
