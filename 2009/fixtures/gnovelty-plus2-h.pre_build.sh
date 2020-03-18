cd /src/gnovelty+2-H
#wget https://sourceforge.net/projects/boost/files/boost/1.38.0/boost_1_38_0.tar.gz/download
wget http://alfweb.net/boost_1_38_0.tar.gz && tar -xzf boost_1_38_0.tar.gz
sed -i '11d' /src/gnovelty+2-H/Makefile
echo "INCFLAGS= -I /src/gnovelty+2-H/boost_1_38_0" > /tmp/tmpfile
cat /tmp/tmpfile /src/gnovelty+2-H/Makefile > /tmp/tmpfile2
mv /tmp/tmpfile2 /src/gnovelty+2-H/Makefile
