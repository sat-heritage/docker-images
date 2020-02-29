ARG BASE
ARG BUILDER_BASE
FROM ${BUILDER_BASE} as builder
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN apt-get update --fix-missing &&\
    apt -y install zip gcc g++ cmake make patch xz-utils zlib1g-dev curl

COPY setup.json fixtures/$solver* /src/

WORKDIR /src

ARG solver
ARG download_url

RUN curl -L $download_url | tar -xvf - -C /src && unzip code.zip

RUN test -f $solver.pre_build.sh && sh $solver.pre_build.sh || true

RUN bash build.sh && mkdir $solver && mv binary $solver/bin

RUN test -f $solver.post_build.sh && sh $solver.post_build.sh || true

FROM ${BASE}
ARG solver

ARG solver_id
ARG IMAGE_NAME
ENV SOLVER=$solver_id \
    DOCKER_IMAGE=$IMAGE_NAME

COPY --from=builder /src/$solver/bin/ /solvers/$solver/

ARG dbjson
COPY $dbjson /solvers/solvers.json
