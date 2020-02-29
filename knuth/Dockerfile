FROM debian:stretch-slim

RUN apt -y update --fix-missing && apt -y install gcc curl make

WORKDIR /src

RUN mkdir cweb && cd cweb && curl -LO ftp://ftp.cs.stanford.edu/pub/cweb/cweb.tar.gz && tar -xvzf cweb.tar.gz && make && cp ctangle cweave /usr/local/bin

RUN mkdir sgb && cd sgb && curl -LO ftp://ftp.cs.stanford.edu/pub/sgb/sgb.tar.gz && tar -xvzf sgb.tar.gz && make tests && make install

ARG solver

WORKDIR /src/${solver}
COPY run.sh /src/${solver}/bin/${solver}

ARG SOURCE_FILE
ADD https://www-cs-faculty.stanford.edu/~knuth/programs/${solver}.w /src/${solver}/

RUN ctangle ${solver}.w
RUN gcc -o bin/${solver}.out ${solver}.c -I/usr/local/sgb/include -L/usr/local/lib -static -lgb

RUN mv /src/${solver}/bin /dist
