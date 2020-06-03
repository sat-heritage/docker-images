set -x
cd src
python configure --extra-include /usr/include/mpi
#python configure --extra-include /usr/include/x86_64-linux-gnu/mpich/
make
