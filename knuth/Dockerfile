FROM debian:stretch-slim

# Debian Stretch has moved to archive.debian.org.
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

RUN apt -y update --fix-missing && apt -y install gcc curl make

WORKDIR /src

RUN mkdir cweb && cd cweb && curl -LO ftp://ftp.cs.stanford.edu/pub/cweb/cweb.tar.gz && tar -xvzf cweb.tar.gz && make && cp ctangle cweave /usr/local/bin

RUN mkdir sgb && cd sgb && curl -LO ftp://ftp.cs.stanford.edu/pub/sgb/sgb.tar.gz && tar -xvzf sgb.tar.gz && make tests && make install

WORKDIR /src

ARG download_url
RUN set -x && curl -fOL "${download_url}"

ARG SOLVER_NAME
RUN set -x && ctangle *.w `find -maxdepth 1 -name '*.ch'` ${SOLVER_NAME}.c && \
    mkdir /dist && \
    gcc -o /dist/${SOLVER_NAME}.out ${SOLVER_NAME}.c -I/usr/local/sgb/include -L/usr/local/lib -static -lgb

COPY run.sh /dist/${SOLVER_NAME}
