chmod +x CaDiCaL/build/build.sh
touch CaDiCaL/starexec_build
echo  "#!/bin/sh" > CadiCal/starexec_build
echo "cd build" >> CadiCal/starexec_build
echo "exec ./build.sh" >> CadiCal/starexec_build
chmod +x CadiCal/starexec_build