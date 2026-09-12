ARG BASE
ARG BUILDER_BASE
FROM ${BUILDER_BASE} as builder

FROM ${BASE}

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
    if ! grep -Eq '^VERSION_ID="?([9]|[1-9][0-9])"?$' /etc/os-release 2>/dev/null; then \
        printf '%s\n' 'Acquire::AllowInsecureRepositories "true";' \
            'APT::Get::AllowUnauthenticated "true";' > /etc/apt/apt.conf.d/99archive-legacy; \
    fi

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
