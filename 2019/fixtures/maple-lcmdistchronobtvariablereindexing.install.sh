set -ex
ls -l
cat > bin/simple_exec <<EOF
#!/bin/bash
#PYTHONPATH="../anaconda3/lib/python3.7"
workingdir=\$PWD
export LD_LIBRARY_PATH="\$LD_LIBRARY_PATH:\$workingdir/../python-igraph-0.7.1.post6/igraphcore/lib/"
../anaconda3/bin/python3.7 variable_index_permutation_preprocessor_wrapper.py --instance \$1
EOF
chmod +x bin/simple_exec
cat > bin/custom_run <<EOF
#!/bin/bash
if [ \$# -eq 2 ]; then
   ./starexec_run_default "\${@}"
else
   ./simple_exec "\${@}"
fi
EOF
chmod +x bin/custom_run
rm *.tar.*
mv -v bin cgraph anaconda3 python-igraph-* /dist/
