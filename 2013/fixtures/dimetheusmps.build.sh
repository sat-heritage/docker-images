!/bin/bash

echo "Starting build operations for DimetheusMPS..."
echo "Loading the globus GCC module. This operation might fail if no globus toolkit is provided. We assume that GCC 4.4. or higher is available."
module load compiler/gnu
echo "Changing directory to ./code/src"
cd ./code/src
echo "Starting compile operations with make"
make
echo "Changing directory to package root"
cd ../../
echo "Creating the binary directory"
mkdir -p binary
rm -rf ./binary/*
echo "Moving the binary to the binary directory"
mv ./code/bin/dimetheus ./binary/DimetheusMPS
echo " "
echo " "