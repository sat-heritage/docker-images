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

FROM ${BASE}

ARG RDEPENDS
RUN if test "${RDEPENDS}"; then apt-get update --fix-missing \
    && apt-get install ${RDEPENDS} \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*; fi

ARG solver
ARG solver_id
ARG IMAGE_NAME
ENV SOLVER=$solver_id \
    DOCKER_IMAGE=$IMAGE_NAME

COPY --from=builder /dist/ /solvers/$solver/

ARG dbjson
COPY $dbjson /solvers/solvers.json
