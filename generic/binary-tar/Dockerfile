FROM debian:stretch-slim AS source
ARG download_url
ADD $download_url /src/bin.tar
WORKDIR /dist
RUN tar xvf /src/bin.tar
