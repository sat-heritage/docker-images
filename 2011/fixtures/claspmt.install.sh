set -ex
cp -v $(find /src/claspmt-2.0-R4095-patched -path "*release_mt/bin/clasp" | head -1) /dist/claspmt; find /src/claspmt-2.0-R4095-patched -name "sat11-port*" -exec cp -v {} /dist/ \; || true
