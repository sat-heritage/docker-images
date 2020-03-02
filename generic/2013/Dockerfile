ARG BASE
ARG BUILDER_BASE
FROM ${BUILDER_BASE} as builder
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN apt-get update --fix-missing &&\
    apt -y install zip gcc g++ cmake make patch xz-utils zlib1g-dev curl

ARG solver
ARG download_url

RUN curl -o $solver.tar -L $download_url \
    && mkdir /src && tar -xvf $solver.tar -C /src \
    && rm $solver.tar

RUN test -f $solver.pre_build.sh && sh $solver.pre_build.sh || true

RUN cd /src && unzip code.zip && e=`find . -name 'build.sh' -printf '%h\n'` && cd ${e} && bash build.sh && mkdir -p /src/$solver && mv binary /src/$solver/bin 

COPY setup.json fixtures/$solver* /src/

WORKDIR /src

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
