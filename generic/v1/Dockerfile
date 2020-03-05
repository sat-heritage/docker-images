#
# The Docker building is done in two stages:
# 1. download and extract asset in /src
# 2. compile the solver in the given BUILDER_BASE and install it in /dist
#
# The extraction tries to detect automatically the archive format
# The compilation tries to detect automatically the building method and
# installation method:
# For the compilation, it tries in this order:
#  - <set>/fixtures/SOLVER.build.sh
#  - <set>/build.sh
#  - build.sh
#  - Makefile
#  - ./configure && make
#
# For the installatin in /dist, it tries in this order:
#  - <set>/fixtures/SOLVER.install.sh
#  - <set>/install.sh
#  - if 'binary' directory exists move its content to /dist
#  - if 'bin' directory exists move its content to /dist
#  - move all executable files at the root of source directory to /dist
#

ARG BUILDER_BASE
ARG PLATFORM

#
# This first part takes care about downloading the archive
# and unpack it in /src.
# It uses a different base from the builder to ease downloading and extraction.
#
FROM debian:stretch-slim as unpack

RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        ca-certificates\
        curl\
        unzip

WORKDIR /assets

ARG download_url
RUN curl -fOL "${download_url}"

WORKDIR /src

# allow for custom unpacking scripts
COPY setup.json unpack*.sh /

RUN ASSET="$(ls /assets/*)" && set -ex && \
    if test -f /unpack.sh; then bash /unpack.sh "${ASSET}"; \
    else ext="${ASSET##*.}" && b="${ASSET%.*}" && \
        if [ "${b##.*}" = "tar" ]; then ext="tar.${ext}" && b="${b%.*}"; fi; \
        case "${ext}" in \
        tgz|tar.gz) tar xvzf "${ASSET}";; \
        zip) unzip "${ASSET}";; \
         *) echo "Unknown archive type!" && exit 1;; esac; fi


#
# This part takes care about compiling the solver
# and installing binaries in /dist
#
FROM ${BUILDER_BASE}
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN apt-get update --fix-missing &&\
    apt-get -y install zip gcc g++ cmake make patch curl zlib1g-dev

ARG BUILD_DEPENDS
RUN if test "${BUILD_DEPENDS}"; then \
    apt-get install -y --no-install-recommends ${BUILD_DEPENDS}; fi

COPY --from=unpack /src /src

WORKDIR /src

ARG SOLVER

COPY setup.json build*.sh install* fixtures/$SOLVER* /

RUN set -ex && if test -f /$SOLVER.pre_build.sh; then bash /$SOLVER.pre_build.sh; fi

RUN set -ex && cd ./`find -maxdepth 1 -mindepth 1 -type d|tail -n1` && \
    if test -f /$SOLVER.build.sh; then bash /$SOLVER.build.sh; \
    elif test -f /build.sh; then bash /build.sh; \
    elif test -f build.sh; then sh build.sh;\
    elif test -f Makefile -o -f makefile; then make;\
    elif test -x configure; then ./configure && make && rm -f configure mkconfig;\
    else echo "did not found any building tool"; exit 1; fi

RUN set -ex && if test -f /$SOLVER.post_build.sh; then bash /$SOLVER.post_build.sh; fi

RUN set -ex && mkdir /dist && cd ./`find -maxdepth 1 -mindepth 1 -type d|tail -n1` && \
    if test -f /$SOLVER.install.sh; then bash /$SOLVER.install.sh; \
    elif test -f /install.sh; then bash /install.sh; \
    elif test -d binary; then mv -v binary/* /dist/; \
    elif test -d bin; then mv -v bin/* /dist/; \
    else find -perm +100 -type f -maxdepth 1 -exec mv -v {} /dist/{} \;; fi

