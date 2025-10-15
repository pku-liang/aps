#!/bin/bash

# Run this script in pixi enviroment by

# ```sh
# pixi s -e aps
# ```

set -e
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
cd ${SCRIPT_DIR}/../

# ===================================================
# 0. Patch Verilator
# ===================================================

TARGET_FILE="${PIXI_PROJECT_ROOT}/.pixi/envs/aps/share/verilator/include/verilated.mk"
sed -i 's|^AR *= *.*|AR = /usr/bin/ar|' "$TARGET_FILE"
sed -i 's|^CXX *= *.*|CXX = /usr/bin/g++|' "$TARGET_FILE"
sed -i 's|^LINK *= *.*|LINK = /usr/bin/g++|' "$TARGET_FILE"

# ===================================================
# 1. Clone Chipyard repository
# ===================================================

git clone git@github.com:pku-liang/aps-chipyard.git
cd aps-chipyard
git checkout aps

./scripts/init-submodules-no-riscv-tools-nolog.sh

cd ${SCRIPT_DIR}/../

# ===================================================
# 2. Install RISC-V toolchain (RV32)
# ===================================================

mkdir bin

# msgfmt in pixi env is not compatible with the toolchain, use system's
ln -s /usr/bin/msgfmt ./bin/msgfmt 

./scripts/init-toolchain-rv32.sh

cd ${SCRIPT_DIR}/../

# ===================================================
# 3. Install RISC-V toolchain extra
# ===================================================

# These patch is applied in build-toolchain-extra-32.sh
# cd ${SCRIPT_DIR}/../aps-chipyard/toolchains/libgloss
# git apply ../aps_rv32_patch/1_libgloss.patch

# cd ${SCRIPT_DIR}/../aps-chipyard/toolchains/riscv-tools/riscv-tests
# git apply ../../aps_rv32_patch/2_riscv-tests.patch

cd ${SCRIPT_DIR}/../aps-chipyard

./scripts/build-toolchain-extra-32.sh -p $RISCV 2>&1 | tee build-toolchain-extra-32.log

echo "=================================================="
echo "Chipyard and RISC-V toolchain (RV32) setup completed."
echo "You can now use the Chipyard environment with the RISC-V toolchain."
echo "=================================================="

# ===================================================
# 4. Clone APS-Synth
# ===================================================

cd ${SCRIPT_DIR}/../

git clone --recursive git@github.com:pku-liang/aps-synth.git aps-synth

# ===================================================
# 5. Clone APS-Croc
# ===================================================

cd ${SCRIPT_DIR}/../

git clone --recursive git@github.com:pku-liang/aps-croc.git aps-croc

# ===================================================
# 6. Install Yosys-slang plugin
# ===================================================

cd ${SCRIPT_DIR}/../

git clone --recursive https://github.com/povik/yosys-slang

cd yosys-slang

mkdir -p build && cd build
cmake .. -GNinja
ninja -j$(nproc)

mkdir -p $(dirname $(which yosys))/../share/plugins

cp slang.so $(dirname $(which yosys))/../share/plugins


# ===================================================
# 7. Clone APSC Compiler
# ===================================================

cd ${SCRIPT_DIR}/../

git clone git@github.com:pku-liang/aps-compiler.git aps-compiler
cd aps-compiler
git submodule update --init --recursive
./build.sh

