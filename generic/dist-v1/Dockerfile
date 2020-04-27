ARG BASE
ARG BUILDER_BASE
FROM ${BUILDER_BASE} as builder

FROM ${BASE}

ARG RDEPENDS
RUN if test "${RDEPENDS}"; then apt-get update --fix-missing && \
    mkdir -p /usr/share/man/man1 && \
    (apt-get install -y --no-install-recommends ${RDEPENDS} ||\
     apt-get install -y ${RDEPENDS}) && \
    apt-get clean -y && rm -rf /var/lib/apt/lists/*; fi

ARG SOLVER
ARG SOLVER_NAME
ARG IMAGE_NAME
ENV SOLVER=$SOLVER \
    DOCKER_IMAGE=$IMAGE_NAME

COPY --from=builder /dist/ /solvers/$SOLVER_NAME/

ARG dbjson
COPY $dbjson /solvers/solvers.json
