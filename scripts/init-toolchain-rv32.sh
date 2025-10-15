#!/bin/bash
mkdir -p $PIXI_PROJECT_ROOT/riscv-toolchain
cd $PIXI_PROJECT_ROOT/riscv-toolchain

mkdir -p $RISCV

git clone https://github.com/riscv-collab/riscv-gnu-toolchain

cd riscv-gnu-toolchain
git checkout 2024.03.01
sed -i 's_https://gcc.gnu_git://gcc.gnu_g' .gitmodules
sed -i 's_https://sourceware.org_git://sourceware.org_g' .gitmodules

./configure --prefix=$RISCV --with-arch=rv32imacfd_zifencei_zicsr --with-abi=ilp32d \
  --with-multilib-generator='rv32i-ilp32--;rv32im-ilp32--;rv32ima-ilp32--;rv32imac-ilp32--;rv32imacf-ilp32f--;rv32imacfd-ilp32d--;rv32imaf-ilp32f--;rv32imafd-ilp32d--'
make -j$(nproc) 2>&1 | tee ../build.log