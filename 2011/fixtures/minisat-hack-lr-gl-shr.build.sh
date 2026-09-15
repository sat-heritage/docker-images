set -ex
cd /src/minisat_LR_GL_SHR && export MROOT=$PWD && cd simp && make r && cp minisat_release ../lr_gl_shr
