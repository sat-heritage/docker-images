ARG BUILDER_BASE
FROM ${BUILDER_BASE} as builder
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN apt-get update --fix-missing &&\
    apt -y install zip gcc g++ cmake make patch xz-utils zlib1g-dev curl

ARG SOLVER_NAME
ARG download_url

RUN curl -o $SOLVER_NAME.zip -L $download_url \
    && unzip $SOLVER_NAME.zip -d /src \
    && rm $SOLVER_NAME.zip

COPY setup.json fixtures/$SOLVER_NAME* /src/

WORKDIR /src

RUN test -f $SOLVER_NAME.pre_build.sh && bash $SOLVER_NAME.pre_build.sh || true

RUN cd /src/$SOLVER_NAME && bash starexec_build

RUN test -f $SOLVER_NAME.post_build.sh && bash $SOLVER_NAME.post_build.sh || true

RUN mv /src/$SOLVER_NAME/bin /dist
