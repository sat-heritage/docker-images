FROM debian:stretch-slim

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
