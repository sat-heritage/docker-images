ARG BASE
FROM ${BASE}
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

ENTRYPOINT ["/entrypoint.sh"]
WORKDIR /data

# A dated snapshot keeps recent competition runtime packages reproducible.
# Without APT_SNAPSHOT, retain the archive fallback used by older entries.
ARG APT_SNAPSHOT
ARG APT_CODENAME
RUN set -eu; \
    mkdir -p /etc/apt/apt.conf.d; \
    if [ -n "${APT_SNAPSHOT:-}" ]; then \
        : "${APT_CODENAME:?APT_CODENAME is required with APT_SNAPSHOT}"; \
        rm -f /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; \
        printf '%s\n' \
            "deb http://snapshot.debian.org/archive/debian/${APT_SNAPSHOT} ${APT_CODENAME} main" \
            "deb http://snapshot.debian.org/archive/debian-security/${APT_SNAPSHOT} ${APT_CODENAME}-security main" \
            > /etc/apt/sources.list; \
        printf '%s\n' 'Acquire::Check-Valid-Until "false";' 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/99snapshot; \
    else \
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
        printf '%s\n' 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99archive; \
        if ! grep -Eq '^VERSION_ID="?([9]|[1-9][0-9])"?$' /etc/os-release 2>/dev/null; then \
            printf '%s\n' 'Acquire::AllowInsecureRepositories "true";' \
                'APT::Get::AllowUnauthenticated "true";' > /etc/apt/apt.conf.d/99archive-legacy; \
        fi; \
    fi

RUN apt-get update --fix-missing &&\
    apt-get install -y --no-install-recommends jq && \
    apt-get clean -y && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /
