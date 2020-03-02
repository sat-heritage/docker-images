ARG BASE
ARG BUILDER_BASE
FROM ${BUILDER_BASE} as builder
ENV LANG=C LC_ALL=C

RUN apt-get update --fix-missing &&\
    apt-get -y install zip gcc g++ cmake make patch curl

ARG BUILD_DEPENDS
RUN if test "${BUILD_DEPENDS}"; then \
    apt-get install -y --no-install-recommends ${BUILD_DEPENDS}; fi

COPY setup.json fixtures/$solver* /src/

ARG solver
ARG solver_id
ARG download_url

WORKDIR /src

ADD $download_url /src/$solver_id.tgz
RUN tar xzf $solver_id.tgz

RUN test -f $solver_id.pre_build.sh && sh $solver_id.pre_build.sh || true

RUN mkdir /dist && cd `ls -d *` && \
    if test -f $solver_id.build.sh; then sh $solver_id.build.sh; else \
    make && find -perm +100 -type f -exec mv -v {} /dist \;; fi

RUN test -f $solver_id.post_build.sh && sh $solver_id.post_build.sh || true
