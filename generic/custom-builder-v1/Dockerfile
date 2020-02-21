ARG BASE
ARG BUILDER_BASE
FROM ${BUILDER_BASE} as builder

FROM ${BASE}
ARG solver

ARG solver_id
ARG IMAGE_NAME
ENV SOLVER=$solver_id \
    DOCKER_IMAGE=$IMAGE_NAME

COPY --from=builder /src/$solver/bin/ /solvers/$solver/

ARG dbjson
COPY $dbjson /solvers/solvers.json
