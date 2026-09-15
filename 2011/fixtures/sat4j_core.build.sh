set -ex
cd /src && rm -rf compile && mkdir compile && cd compile && unzip -q ../sat4j-core-v20110206.zip && rm -f org.sat4j.core.jar && jar xf org.sat4j.core-src.jar && cp ../sat11-12-leberre.build.xml build.xml && ant
