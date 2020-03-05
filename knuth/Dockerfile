FROM debian:stretch-slim

RUN apt -y update --fix-missing && apt -y install gcc curl make

WORKDIR /src

RUN mkdir cweb && cd cweb && curl -LO ftp://ftp.cs.stanford.edu/pub/cweb/cweb.tar.gz && tar -xvzf cweb.tar.gz && make && cp ctangle cweave /usr/local/bin

RUN mkdir sgb && cd sgb && curl -LO ftp://ftp.cs.stanford.edu/pub/sgb/sgb.tar.gz && tar -xvzf sgb.tar.gz && make tests && make install

ARG SOLVER_NAME

WORKDIR /src

ADD https://www-cs-faculty.stanford.edu/~knuth/programs/${SOLVER_NAME}.w /src/

RUN ctangle ${SOLVER_NAME}.w && \
    mkdir bin && \
    gcc -o bin/${SOLVER_NAME}.out ${SOLVER_NAME}.c -I/usr/local/sgb/include -L/usr/local/lib -static -lgb

RUN mv bin /dist
COPY run.sh /dist/${SOLVER_NAME}
