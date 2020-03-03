ARG BUILDER_BASE
FROM ${BUILDER_BASE}
ARG download_url
ADD $download_url /dist/
ARG solver
RUN find /dist; chmod -v +x /dist/*
