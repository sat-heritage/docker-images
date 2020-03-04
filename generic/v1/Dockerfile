#
# The Docker building is done in two stages:
# 1. download and extract asset in /src
# 2. compile the solver in the given BUILDER_BASE and install it in /dist
#

ARG BUILDER_BASE

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
        if [[ "${b##.*}" == "tar" ]]; then ext="tar.${ext}" && b="${b%.*}"; fi; \
        case "${ext}" in \
        tgz|tar.gz) tar xvzf "${ASSET}";; \
        zip) unzip "${ASSET}";; \
         *) echo "Unknown archive type!" && exit 1;; esac; fi


#
# This part takes care about compiling the solver
# and installing binaries in /dist
#
FROM ${BUILDER_BASE}
ENV LANG=C LC_ALL=C

RUN apt-get update --fix-missing &&\
    apt-get -y install zip gcc g++ cmake make patch curl zlib1g-dev

ARG BUILD_DEPENDS
RUN if test "${BUILD_DEPENDS}"; then \
    apt-get install -y --no-install-recommends ${BUILD_DEPENDS}; fi

COPY --from=unpack /src /src

WORKDIR /src

ARG SOLVER

COPY setup.json build*.sh fixtures/$SOLVER* /

RUN set -x && test -f /$SOLVER.pre_build.sh && bash /$SOLVER.pre_build.sh || true

RUN set -ex && mkdir /dist && cd `find -maxdepth 1 -mindepth 1 -type d` && \
    if test -f /$SOLVER.build.sh; then bash /$SOLVER.build.sh; \
    elif test -f /build.sh; then bash /build.sh; else \
    if test -f Makefile; then make;\
    elif test -f build.sh; then sh build.sh;\
    else echo "did not found any building tool"; exit 1; fi; \
    find -perm +100 -type f -exec mv -v {} /dist \;; fi

RUN set -x && test -f /$SOLVER.post_build.sh && bash /$SOLVER.post_build.sh || true

