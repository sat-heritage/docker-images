ARG BUILDER_BASE
FROM ${BUILDER_BASE} AS buildenv
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

# Debian releases used by historical solvers have moved to archive.debian.org.
RUN set -eu; \
    for list in /etc/apt/sources.list /etc/apt/sources.list.d/*.list; do \
        if [ -f "$list" ]; then \
            sed \
                -e 's|https\?://deb.debian.org/debian-security|http://archive.debian.org/debian-security|g' \
                -e 's|https\?://security.debian.org/debian-security|http://archive.debian.org/debian-security|g' \
                -e 's|https\?://security.debian.org|http://archive.debian.org/debian-security|g' \
                -e 's|https\?://deb.debian.org/debian|http://archive.debian.org/debian|g' \
                -e 's|https\?://ftp.debian.org/debian|http://archive.debian.org/debian|g' \
                -e 's|https\?://httpredir.debian.org/debian|http://archive.debian.org/debian|g' \
                -e '/-updates[[:space:]]/d' \
                "$list" > "$list.archive"; \
            mv "$list.archive" "$list"; \
        fi; \
    done; \
    mkdir -p /etc/apt/apt.conf.d; \
    printf '%s\n' 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99archive; \
    if ! grep -Eq '^VERSION_ID="?(1[0-9])"?$' /etc/os-release 2>/dev/null; then \
        printf '%s\n' 'Acquire::AllowInsecureRepositories "true";' \
            'APT::Get::AllowUnauthenticated "true";' > /etc/apt/apt.conf.d/99archive-legacy; \
    fi

RUN apt-get update --fix-missing &&\
    apt -y install zip gcc g++ cmake make patch xz-utils zlib1g-dev curl

FROM buildenv AS source

ARG SOLVER_NAME
ARG download_url

RUN curl -o $SOLVER_NAME.zip -L $download_url \
    && unzip $SOLVER_NAME.zip -d /src \
    && rm $SOLVER_NAME.zip

COPY setup.json fixture[s]/$SOLVER_NAME* /src/

FROM source AS builder

ARG SOLVER_NAME
WORKDIR /src

RUN test -f $SOLVER_NAME.pre_build.sh && bash $SOLVER_NAME.pre_build.sh || true

RUN cd /src/$SOLVER_NAME && bash starexec_build

RUN test -f $SOLVER_NAME.post_build.sh && bash $SOLVER_NAME.post_build.sh || true

RUN mv /src/$SOLVER_NAME/bin /dist
