ARG BASE
FROM ${BASE}

ARG RDEPENDS
RUN if test "${RDEPENDS}"; then \
    apt-get update --fix-missing \
    && apt-get install ${RDEPENDS} \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*; fi

ARG solver
ARG solver_id
ARG IMAGE_NAME
ENV SOLVER=$solver_id \
    DOCKER_IMAGE=$IMAGE_NAME

ARG download_url
ADD $download_url /solvers/$solver/
RUN find /solvers; chmod +x /solvers/$solver/$solver

ARG dbjson
COPY $dbjson /solvers/solvers.json
