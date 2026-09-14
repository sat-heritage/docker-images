ARG BUILDER_BASE

FROM ${BUILDER_BASE} AS buildenv
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

# Rebuild with the packages that were available at competition time.  The
# snapshot is optional so this builder can also be reused by older entries.
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
    fi; \
    apt-get update --fix-missing; \
    apt-get install -y --no-install-recommends \
      bash ca-certificates cmake curl g++ gcc make patch unzip xz-utils zlib1g-dev; \
    rm -rf /var/lib/apt/lists/*

ARG BUILD_DEPENDS
RUN if [ -n "${BUILD_DEPENDS:-}" ]; then \
      apt-get update --fix-missing && \
      apt-get install -y --no-install-recommends ${BUILD_DEPENDS} && \
      rm -rf /var/lib/apt/lists/*; \
    fi

FROM buildenv AS source
ARG download_url
# Release assets are ZIP files for ZIP competition distributions and tar.xz
# files otherwise; both unpack to /src/<solver name>/.
RUN mkdir -p /src && \
    curl --fail --location --retry 3 --output /tmp/submission "${download_url}" && \
    if unzip -tq /tmp/submission >/dev/null 2>&1; then \
        unzip -q /tmp/submission -d /src; \
    else \
        tar -xf /tmp/submission -C /src; \
    fi && \
    rm /tmp/submission

FROM source AS builder
# Build as an unprivileged user, like StarExec does: some submitted build
# scripts run the solver's own test suite, which refuses to run as root.
RUN useradd --create-home --shell /bin/bash builder && \
    mkdir -p /dist && chown -R builder:builder /src /dist
USER builder
ARG SOLVER_NAME
ARG BUILD_KIND=auto
ARG BUILD_SUBDIR=.
ARG BUILD_SCRIPT=build.sh
ARG BUILD_ARGS=
ARG CONFIGURE_ARGS=
ARG MAKE_ARGS=
ARG BUILD_COMMAND=
ARG BUILD_ENV=
ARG BINARY_PATH
ARG BINARY_NAME
ARG DIST_PATHS=

WORKDIR /src

# Competition ZIP files do not reliably preserve executable bits.  Invoke the
# submitted instructions through a shell and restore permissions on helpers.
RUN set -eu; \
    root="/src/${SOLVER_NAME}"; \
    test -d "$root"; \
    find "$root" -type f \( -name configure -o -name 'starexec_build*' -o -name '*.sh' \) \
      -exec chmod +x {} \;; \
    cd "$root/$BUILD_SUBDIR"; \
    if [ -n "$BUILD_ENV" ]; then eval "export $BUILD_ENV"; fi; \
    kind="$BUILD_KIND"; \
    if [ "$kind" = auto ]; then \
      if [ -f starexec_build ]; then kind=starexec; \
      elif [ -f build/build.sh ]; then kind=build-subdir; \
      elif [ -f configure ]; then kind=configure; \
      elif [ -f Makefile ] || [ -f makefile ]; then kind=make; \
      else echo 'no supported StarExec build instructions found' >&2; exit 1; fi; \
    fi; \
    case "$kind" in \
      starexec) bash ./starexec_build ${BUILD_ARGS} ;; \
      build-subdir) cd build; bash ./build.sh ${BUILD_ARGS} ;; \
      script) bash "./${BUILD_SCRIPT}" ${BUILD_ARGS} ;; \
      configure) sh ./configure ${CONFIGURE_ARGS}; make ${MAKE_ARGS} ;; \
      make) make ${MAKE_ARGS} ;; \
      command) bash -ec "$BUILD_COMMAND" ;; \
      *) echo "unsupported BUILD_KIND: $kind" >&2; exit 1 ;; \
    esac; \
    mkdir -p /dist; \
    if [ -n "$BINARY_PATH" ]; then \
        test -f "$root/$BINARY_PATH"; \
        install -m 0755 "$root/$BINARY_PATH" "/dist/${BINARY_NAME:-$(basename "$BINARY_PATH")}"; \
        test -x "/dist/${BINARY_NAME:-$(basename "$BINARY_PATH")}"; \
    fi; \
    for path in $DIST_PATHS; do \
        test -e "$root/$path"; \
        mkdir -p "/dist/$(dirname "$path")"; \
        cp -a "$root/$path" "/dist/$path"; \
    done; \
    test -n "$BINARY_PATH$DIST_PATHS"
