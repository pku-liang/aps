#!/usr/bin/env python3
"""
Automatic Makefile generator for APS projects.
Reads configuration from YAML file and generates a Makefile based on templates.
"""

import yaml
import os
import argparse
from pathlib import Path
import traceback

class MakefileGenerator:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self._load_config()
        if self._get_param('general', 'platform', None) not in ["croc", "rocc"]:
            raise ValueError("Only support platform: croc and rocc")
        
    def _load_config(self):
        """Load and parse YAML configuration file."""
        script_dir = Path(__file__).parent
        config_file = script_dir / 'workspace' / 'configs' / f'{self.config_path}.yml'
        try:
            with open(config_file, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration: {e}")
    
    def _get_param(self, section, key, default=None):
        """Get parameter from config with default fallback."""
        if section in self.config and self.config[section] is not None and key in self.config[section]:
            return self.config[section][key]
        return default
    
    def _format_makefile_var(self, name, value, indent=0):
        """Format a Makefile variable assignment."""
        spaces = ' ' * indent
        if isinstance(value, bool):
            value = str(value).lower()
        elif isinstance(value, str):
            value = f'"{value}"'
        return f"{spaces}{name} := {value}"
    
    def _generate_variables_section(self):
        """Generate the variables/parameters section of the Makefile."""
        # For CROC projects, use cvxif architecture in synthesis
        platform = self._get_param('general', 'platform', 'rocc')
        arch = 'cvxif' if platform == 'croc' else platform
        
        lines = [
            "###########################################################",
            "# Parameters",
            "###########################################################",
            "",
            "## General",
            f"PWD\t\t\t\t:= $(dir $(abspath $(lastword $(MAKEFILE_LIST))))",
            f"PROJ\t\t\t\t:= {self._get_param('general', 'proj', 'project')}",
            f"CADL_FILE\t:= cadl/{self._get_param('general', 'cadl', 'design.cadl')}",
            f"C_FILE\t\t\t:= csrc/{self._get_param('general', 'c_file', 'main.c')}",
            f"C_FUNC_EVAL\t:= {self._get_param('general', 'c_func_eval', 'main')}",
            f"ARCH\t\t\t\t:= {arch}",
            "",
            "## Synth",
            f"SYN_TARGET_PERIOD\t:= {self._get_param('synthesis', 'target-period', 6.0)}",
            f"SYN_AGGRESSIVE\t:= {str(self._get_param('synthesis', 'aggressive', False)).lower()}",
            "",
            "## Compile",
            f"COMPILE_OPT_LEVEL\t:= {self._get_param('compile', 'optimization_level', 'O3')}",
            "",
            "## ASIC",
            f"ASIC_TARGET_PERIOD\t:= {self._get_param('asic', 'target-period', 6.0)}",
            "",
        ]
        return '\n'.join(lines)
    
    def _generate_targets_section(self):
        """Generate the targets section of the Makefile."""
        # Set different all target dependencies based on platform
        all_targets = "all: synth compile sim"
            
        lines = [
            "###########################################################",
            "# Targets",
            "###########################################################",
            "",
            "define PRINT_OK",
            "\t@echo \"\\033[0;32m         ________  ___  __       \"",
            "\t@echo '        |\\   __  \\|\\  \\|\\  \\     '",
            "\t@echo '        \\ \\  \\|\\  \\ \\  \\/  /|_   '",
            "\t@echo '         \\ \\  \\\\\\  \\ \\   ___  \\  '",
            "\t@echo '          \\ \\  \\\\\\  \\ \\  \\\\ \\  \\ '",
            "\t@echo '           \\ \\_______\\ \\__\\\\ \\__\\'",
            "\t@echo '            \\|_______|\\|__| \\|__|'",
            "\t@echo \"                                 \\033[0m\"",
            "endef",
            "",
            all_targets,
            "\t@echo \"\\033[0;32m[BUILD-ALL] All tasks completed successfully!\\033[0m\"",
            "",
            "default: all",
            "",
        ]
        return '\n'.join(lines)
    
    def _generate_synthesis_section(self):
        """Generate the synthesis section of the Makefile."""
        lines = [
            "## Synthesis",
            "SYNTH_OUTPUT_PATH := out/verilog",
            "SYNTH_REPORT_PATH := report/synth",
            "SYNTH_OUTPUT_SV := $(SYNTH_OUTPUT_PATH)/$(PROJ).sv",
            "SYNTH_OUTPUT_JSON := $(SYNTH_OUTPUT_PATH)/synth.json",
            "SYNTH_OUTPUT_SEMANTIC := $(SYNTH_OUTPUT_PATH)/semantic.json",
            "SYNTH_OUTPUT_FIR := $(SYNTH_OUTPUT_PATH)/$(PROJ).fir",
            "",
            "$(SYNTH_OUTPUT_SV): $(CADL_FILE)",
            "\t@echo \"\\033[0;32m[SYNTH] Starting synthesis for $(PROJ)...\\033[0m\"",
            "\t@mkdir -p $(SYNTH_OUTPUT_PATH)",
            "\t@mkdir -p $(SYNTH_REPORT_PATH)",
            "\t@echo \"\\033[0;32m[SYNTH] Running aps synth command...\\033[0m\"",
            "\t@cd ../../aps-synth && \\",
            "\t\tRUSTFLAGS=\"-Awarnings\" cargo run --quiet --bin aps -- -i $(realpath $(CADL_FILE)) \\",
            "\t\t-a $(ARCH) synth --output-sv $(PWD)/$(SYNTH_OUTPUT_SV) \\",
            "\t\t--output-backend $(PWD)/$(SYNTH_OUTPUT_JSON) \\",
            "\t\t--target-period $(SYN_TARGET_PERIOD) \\",
            "\t\t$(if $(filter true,$(SYN_AGGRESSIVE)),--aggressive-timing,) \\",
            "\t\t--report-path $(PWD)/$(SYNTH_REPORT_PATH) || \\",
            "\t{ echo \"\\033[0;31m[SYNTHESIS FAILED]\\033[0m\"; exit 1; }",
            "\t@echo \"\\033[0;32m[SYNTH] Running aps export command...\\033[0m\"",
            "\t@cd ../../aps-synth && \\",
            "\tRUSTFLAGS=\"-Awarnings\" cargo run --bin aps -- -i $(realpath $(CADL_FILE)) -a $(ARCH) export || \\",
            "\t{ echo \"\\033[0;31m[SYNTHESIS FAILED]\\033[0m\"; exit 1; }",
            "\t@cp ../../aps-synth/__generated/arch.json $(SYNTH_OUTPUT_SEMANTIC) || \\",
            "\t{ echo \"\\033[0;31m[SYNTHESIS FAILED]\\033[0m\"; exit 1; }",
            "",
            "$(SYNTH_OUTPUT_JSON): $(SYNTH_OUTPUT_SV)",
            "$(SYNTH_OUTPUT_SEMANTIC): $(SYNTH_OUTPUT_SV)",
            "",
            "synth: $(SYNTH_OUTPUT_SV)",
            "\t@echo \"\\033[0;32m[SYNTH] =================================================================\\033[0m\"",
            "\t$(PRINT_OK)",
            "\t@echo \"\\033[0;32m[SYNTH] Synthesis completed successfully!\\033[0m\"",
            "\t@echo \"\\033[0;32m[SYNTH] Reports located at $(abspath $(SYNTH_REPORT_PATH))/summary.md\\033[0m\"",
            "\t@echo \"\\033[0;32m[SYNTH] \\033[0m\"",
            "\t@echo \"\\033[0;32m[SYNTH] =================================================================\\033[0m\"",
            "",
            "clean-synth:",
            "\t@echo \"[CLEAN] Cleaning synthesis outputs...\"",
            "\t@rm -rf $(realpath $(SYNTH_OUTPUT_PATH)) $(realpath $(SYNTH_REPORT_PATH))",
            "\t@echo \"[CLEAN] Synthesis cleanup completed!\"",
            "",
        ]
        return '\n'.join(lines)
    
    def _generate_compile_section_chipyard(self):
        """Generate the compile section of the Makefile."""
        lines = [
            "## Compile",
            "COMPILE_OUTPUT_PATH := out/sw",
            "COMPILE_REPORT_PATH := report/compile",
            "COMPILE_PATTERN_MATCH_SCRIPT_PATH := ../../aps-compiler/Opt/PatternMatch/Parser",
            "COMPILE_OUTPUT_LL_UNOPT := out/sw/$(PROJ)_unopt.ll",
            "COMPILE_OUTPUT_LL_OPT := out/sw/$(PROJ)_opt.ll",
            "COMPILE_OUTPUT_ASM := out/sw/$(PROJ).S",
            "# COMPILE_OUTPUTS = $(COMPILE_OUTPUT_LL_UNOPT) $(COMPILE_OUTPUT_LL_OPT) $(COMPILE_OUTPUT_ASM)",
            "",
            "$(COMPILE_OUTPUT_ASM): $(C_FILE)",
            "\t@echo \"\\033[0;32m[COMPILE-OPT] Starting compilation for $(PROJ)...\\033[0m\"",
            "\t@cp $(SYNTH_OUTPUT_SEMANTIC) ../../aps-compiler/cache/arch.json",
            "\t@cp $(C_FILE) ../../aps-compiler/examples/$(PROJ).c",
            "\t@mkdir -p $(COMPILE_OUTPUT_PATH)",
            "\t@mkdir -p $(COMPILE_REPORT_PATH)",
            "\t@cd $(COMPILE_PATTERN_MATCH_SCRIPT_PATH) && python test_main.py && \\",
            "\t\t{ echo \"\\033[0;32m[COMPILE-OPT] Successfully parsed CADL semantics, matcher function generated.\\033[0m\"; } || \\",
            "\t\t{ echo \"\\033[0;33m[COMPILE-OPT] CADL is too complex for semantic-based matching. Using profile-based matching now...\\033[0m\"; \\",
            "\t\t\techo \"#include \\\"semantic_result.hpp\\\"\\n\\nstd::unordered_map<std::string, Instruction* (*)(Function *,std::unordered_set<Value *> &,Value* &,Value* &)> func_map = {};\" > $(abspath $(COMPILE_PATTERN_MATCH_SCRIPT_PATH))/../semantic_result.cpp; \\",
            "\t\t\techo \"#include \\\"PatMatch.hpp\\\"\\n\\nextern std::unordered_map<std::string, Instruction* (*)(Function *,std::unordered_set<Value *> &,Value* &,Value* &)> func_map;\" > $(abspath $(COMPILE_PATTERN_MATCH_SCRIPT_PATH))/../semantic_result.hpp; \\",
            "\t\t\techo \"\" > $(abspath $(COMPILE_PATTERN_MATCH_SCRIPT_PATH))/../offline_gen/module_info.json; \\",
            "\t\t}",
            "\t@echo \"\\033[0;32m[COMPILE-OPT] Building customized compiler...\\033[0m\"",
            "\t@cd ../../aps-compiler && ./build.sh || { echo \"\\033[0;31mCOMPILER BUILD FAILED\\033[0m\"; exit 1;}",
            "\t@echo \"\\033[0;32m[COMPILE-OPT] Running compiler script...\\033[0m\"",
            "\t@cd ../../aps-compiler && bash ./compile.sh $(PROJ) $(PWD)/$(COMPILE_OUTPUT_PATH) $(COMPILE_OPT_LEVEL) || { echo \"\\033[0;31mCOMPILE FAILED\\033[0m\"; exit 1;}",
            "\t@mv out/sw/output.S $(COMPILE_OUTPUT_ASM)",
            "\t@mv ../../aps-compiler/examples/combine.ll $(COMPILE_OUTPUT_LL_UNOPT)",
            "\t@mv ../../aps-compiler/examples/output.ll $(COMPILE_OUTPUT_LL_OPT)",
            "\t@mv ../../aps-compiler/pattern_match_info $(COMPILE_REPORT_PATH)/$(PROJ)_patmatch.rpt || \\",
            "\t\t{ echo \"No pattern match applied to this source code\\n\" > $(COMPILE_REPORT_PATH)/$(PROJ)_patmatch.rpt; }",
            "\t@mv ../../aps-compiler/vectorize_info $(COMPILE_REPORT_PATH)/$(PROJ)_vec.rpt || \\",
            "\t\t{ echo \"No vectorization opt applied to this source code\\n\" > $(COMPILE_REPORT_PATH)/$(PROJ)_vec.rpt; }",
            "\t@echo \"\\033[0;32m[COMPILE-OPT] Compilation completed successfully!\\033[0m\"",
            "",
            "$(COMPILE_OUTPUT_LL_UNOPT): $(COMPILE_OUTPUT_ASM)",
            "$(COMPILE_OUTPUT_LL_OPT): $(COMPILE_OUTPUT_ASM)",
            "",
            "compile-asm: $(COMPILE_OUTPUT_ASM)",
            "",
            "COMPILE_ELF_UNOPT_O = out/sw/$(PROJ)_unopt.o",
            "COMPILE_ELF_UNOPT = out/sw/$(PROJ)_unopt.elf",
            "$(COMPILE_ELF_UNOPT): $(C_FILE)",
            "\t@echo \"\\033[0;32m[COMPILE-ELF-UNOPT] Starting unoptimized(baseline) ELF compilation...\\033[0m\"",
            "\t@mkdir -p $(COMPILE_OUTPUT_PATH)",
            "\t@echo \"\\033[0;32m[COMPILE-ELF-UNOPT] Compiling C source to object file...\\033[0m\"",
            "\t@riscv32-unknown-elf-gcc -std=gnu99 -$(COMPILE_OPT_LEVEL) -Wall -Wextra -fno-common -fno-builtin-printf \\",
            "\t\t-march=rv32ima_zicsr_zifencei -mabi=ilp32 -mcmodel=medany -specs=htif_nano.specs \\",
            "\t\t-o $(COMPILE_ELF_UNOPT_O) -c $(C_FILE) || { echo \"\\033[0;31mCOMPILE FAILED\\033[0m\"; exit 1;}",
            "\t@echo \"\\033[0;32m[COMPILE-ELF-UNOPT] Linking object file to ELF...\\033[0m\"",
            "\t@riscv32-unknown-elf-gcc -static -specs=htif_nano.specs \\",
            "\t\t-march=rv32ima_zicsr_zifencei -mabi=ilp32 -mcmodel=medany -T ../../aps-chipyard/tests/htif.ld \\",
            "\t\t$(COMPILE_ELF_UNOPT_O) \\",
            "\t\t-o $(COMPILE_ELF_UNOPT) || { echo \"\\033[0;31mCOMPILE FAILED\\033[0m\"; exit 1;}",
            "\t@rm $(COMPILE_ELF_UNOPT_O)",
            "\t@echo \"\\033[0;32m[COMPILE-ELF-UNOPT] Unoptimized(baseline) ELF compilation completed!\\033[0m\"",
            "",
            "compile-rocket-unopt: $(COMPILE_ELF_UNOPT)",
            "",
            "COMPILE_ELF_OPT_O = out/sw/$(PROJ)_opt.o",
            "COMPILE_ELF_OPT = out/sw/$(PROJ)_opt.elf",
            "$(COMPILE_ELF_OPT): $(COMPILE_OUTPUT_ASM)",
            "\t@echo \"\\033[0;32m[COMPILE-ELF-OPT] Starting optimized ELF compilation...\\033[0m\"",
            "\t@mkdir -p $(COMPILE_OUTPUT_PATH)",
            "\t@echo \"\\033[0;32m[COMPILE-ELF-OPT] Compiling assembly to object file...\\033[0m\"",
            "\t@riscv32-unknown-elf-gcc -std=gnu99 -$(COMPILE_OPT_LEVEL) -Wall -Wextra -fno-common -fno-builtin-printf \\",
            "\t\t-march=rv32ima_zicsr_zifencei -mabi=ilp32 -mcmodel=medany -specs=htif_nano.specs \\",
            "\t\t-o $(COMPILE_ELF_OPT_O) -c $(COMPILE_OUTPUT_ASM) || { echo \"\\033[0;31mCOMPILE FAILED\\033[0m\"; exit 1;}",
            "\t@echo \"\\033[0;32m[COMPILE-ELF-OPT] Linking object file to ELF...\\033[0m\"",
            "\t@riscv32-unknown-elf-gcc -static -specs=htif_nano.specs \\",
            "\t\t-march=rv32ima_zicsr_zifencei -mabi=ilp32 -mcmodel=medany -T ../../aps-chipyard/tests/htif.ld \\",
            "\t\t$(COMPILE_ELF_OPT_O) \\",
            "\t\t-o $(COMPILE_ELF_OPT) || { echo \"\\033[0;31mCOMPILE FAILED\\033[0m\"; exit 1;}",
            "\t@rm $(COMPILE_ELF_OPT_O)",
            "\t@echo \"\\033[0;32m[COMPILE-ELF-OPT] Optimized ELF compilation completed!\\033[0m\"",
            "",
            "compile-rocket-opt: $(COMPILE_ELF_OPT)",
            "",
            "compile: compile-rocket-unopt compile-rocket-opt",
            "\t@echo \"\\033[0;32m[COMPILE] =====================================================================================\\033[0m\"",
            "\t$(PRINT_OK)",
            "\t@echo \"\\033[0;32m[COMPILE] Compilation completed successfully!\\033[0m\"",
            "\t@echo \"\\033[0;32m[COMPILE] Reports located at $(PWD)/$(COMPILE_REPORT_PATH)/$(PROJ)_patmatch.rpt\\033[0m\"",
            "\t@echo \"\\033[0;32m[COMPILE] and $(PWD)/$(COMPILE_REPORT_PATH)/$(PROJ)_vec.rpt\\033[0m\"",
            "\t@echo \"\\033[0;32m[COMPILE] \\033[0m\"",
            "\t@echo \"\\033[0;32m[COMPILE] =====================================================================================\\033[0m\"",
            "",
            "clean-compile:",
            "\t@echo \"[CLEAN] Cleaning compilation outputs...\"",
            "\t@rm -rf $(realpath $(COMPILE_OUTPUT_PATH)) $(realpath $(COMPILE_REPORT_PATH))",
            "\t@echo \"[CLEAN] Compilation cleanup completed!\"",
            "",
        ]
        return '\n'.join(lines)
    
    def _generate_compile_section_croc(self):
        """Generate the compile section of the Makefile."""
        lines = [
            "## Compile",
            "COMPILE_OUTPUT_PATH := out/sw",
            "COMPILE_REPORT_PATH := report/compile",
            "COMPILE_PATTERN_MATCH_SCRIPT_PATH := ../../aps-compiler/Opt/PatternMatch/Parser",
            "COMPILE_OUTPUT_LL_UNOPT := out/sw/$(PROJ)_unopt.ll",
            "COMPILE_OUTPUT_LL_OPT := out/sw/$(PROJ)_opt.ll",
            "COMPILE_OUTPUT_ASM := out/sw/$(PROJ).S",
            "# COMPILE_OUTPUTS = $(COMPILE_OUTPUT_LL_UNOPT) $(COMPILE_OUTPUT_LL_OPT) $(COMPILE_OUTPUT_ASM)",
            "",
            "$(COMPILE_OUTPUT_ASM): $(C_FILE)",
            "\t@echo \"\\033[0;32m[COMPILE-OPT] Starting compilation for $(PROJ)...\\033[0m\"",
            "\t@cp $(SYNTH_OUTPUT_SEMANTIC) ../../aps-compiler/cache/arch.json",
            "\t@cp $(C_FILE) ../../aps-compiler/examples/$(PROJ).c",
            "\t@mkdir -p $(COMPILE_OUTPUT_PATH)",
            "\t@mkdir -p $(COMPILE_REPORT_PATH)",
            "\t@cd $(COMPILE_PATTERN_MATCH_SCRIPT_PATH) && python test_main.py && \\",
            "\t\t{ echo \"\\033[0;32m[COMPILE-OPT] Successfully parsed CADL semantics, matcher function generated.\\033[0m\"; } || \\",
            "\t\t{ echo \"\\033[0;33m[COMPILE-OPT] CADL is too complex for semantic-based matching. Using profile-based matching now...\\033[0m\"; \\",
            "\t\t\techo \"#include \\\"semantic_result.hpp\\\"\\n\\nstd::unordered_map<std::string, Instruction* (*)(Function *,std::unordered_set<Value *> &,Value* &,Value* &)> func_map = {};\" > $(abspath $(COMPILE_PATTERN_MATCH_SCRIPT_PATH))/../semantic_result.cpp; \\",
            "\t\t\techo \"#include \\\"PatMatch.hpp\\\"\\n\\nextern std::unordered_map<std::string, Instruction* (*)(Function *,std::unordered_set<Value *> &,Value* &,Value* &)> func_map;\" > $(abspath $(COMPILE_PATTERN_MATCH_SCRIPT_PATH))/../semantic_result.hpp; \\",
            "\t\t\techo \"\" > $(abspath $(COMPILE_PATTERN_MATCH_SCRIPT_PATH))/../offline_gen/module_info.json; \\",
            "\t\t}",
            "\t@echo \"\\033[0;32m[COMPILE-OPT] Building customized compiler...\\033[0m\"",
            "\t@cd ../../aps-compiler && ./build.sh || { echo \"\\033[0;31mCOMPILER BUILD FAILED\\033[0m\"; exit 1;}",
            "\t@echo \"\\033[0;32m[COMPILE-OPT] Running compiler script...\\033[0m\"",
            "\t@cd ../../aps-compiler && bash ./compile.sh $(PROJ) $(PWD)/$(COMPILE_OUTPUT_PATH) $(COMPILE_OPT_LEVEL) || { echo \"\\033[0;31mCOMPILE FAILED\\033[0m\"; exit 1;}",
            "\t@mv out/sw/output.S $(COMPILE_OUTPUT_ASM)",
            "\t@mv ../../aps-compiler/examples/combine.ll $(COMPILE_OUTPUT_LL_UNOPT)",
            "\t@mv ../../aps-compiler/examples/output.ll $(COMPILE_OUTPUT_LL_OPT)",
            "\t@mv ../../aps-compiler/pattern_match_info $(COMPILE_REPORT_PATH)/$(PROJ)_patmatch.rpt || \\",
            "\t\t{ echo \"No pattern match applied to this source code\\n\" > $(COMPILE_REPORT_PATH)/$(PROJ)_patmatch.rpt; }",
            "\t@mv ../../aps-compiler/vectorize_info $(COMPILE_REPORT_PATH)/$(PROJ)_vec.rpt || \\",
            "\t\t{ echo \"No vectorization opt applied to this source code\\n\" > $(COMPILE_REPORT_PATH)/$(PROJ)_vec.rpt; }",
            "\t@echo \"\\033[0;32m[COMPILE-OPT] Compilation completed successfully!\\033[0m\"",
            "",
            "compile-asm: $(COMPILE_OUTPUTS)",
            "",
            "CROC_PATH = ../../aps-croc",
            "LIB_SRCS = $(wildcard $(CROC_PATH)/sw/lib/src/*.c)",
            "LIB_INCS = $(CROC_PATH)/sw/lib/inc",
            "LIB_LD = $(CROC_PATH)/sw/link.ld",
            "",
            "COMPILE_ELF_UNOPT_O = out/sw/$(PROJ)_unopt.o",
            "COMPILE_ELF_UNOPT = out/sw/$(PROJ)_unopt.elf",
            "COMPILE_HEX_UNOPT = out/sw/$(PROJ)_unopt.hex",
            "$(COMPILE_ELF_UNOPT): $(CROC_PATH)/sw/crt0.S $(LIB_SRCS) $(C_FILE) ",
            "\t@echo \"\\033[0;32m[COMPILE-ELF-UNOPT] Starting unoptimized(baseline) ELF compilation...\\033[0m\"",
            "\t@mkdir -p $(COMPILE_OUTPUT_PATH)",
            "\t@riscv32-unknown-elf-gcc \\",
            "\t\t-march=rv32ima_zicsr_zifencei -mabi=ilp32 -mcmodel=medany \\",
            "\t\t-std=gnu99 -$(COMPILE_OPT_LEVEL) -nostdlib -fno-builtin -ffreestanding \\",
            "\t\t-I$(abspath $(LIB_INCS)) \\",
            "\t\t-I$(abspath $(LIB_INCS))/../../ \\",
            "\t\t-T$(abspath $(LIB_LD)) $^ -o $@ \\",
            "\t\t-nostartfiles -lm -lgcc -static -specs=nano.specs \\",
            "\t\t|| { echo \"\\033[0;31mCOMPILE FAILED\\033[0m\"; exit 1; }",
            "\t@echo \"\\033[0;32m[COMPILE-ELF-UNOPT] Unoptimized(baseline) ELF compilation completed!\\033[0m\"",
            "",
            "compile-croc-unopt: $(COMPILE_ELF_UNOPT)",
            "",
            "COMPILE_ELF_OPT_O = out/sw/$(PROJ)_opt.o",
            "COMPILE_ELF_OPT = out/sw/$(PROJ)_opt.elf",
            "COMPILE_HEX_OPT = out/sw/$(PROJ)_opt.hex",
            "$(COMPILE_ELF_OPT): $(CROC_PATH)/sw/crt0.S $(LIB_SRCS) $(COMPILE_OUTPUT_ASM)",
            "\t@echo \"\\033[0;32m[COMPILE-ELF-OPT] Starting optimized ELF compilation...\\033[0m\"",
            "\t@mkdir -p $(COMPILE_OUTPUT_PATH)",
            "\t@riscv32-unknown-elf-gcc \\",
            "\t\t-march=rv32ima_zicsr_zifencei -mabi=ilp32 -mcmodel=medany \\",
            "\t\t-std=gnu99 -$(COMPILE_OPT_LEVEL) -nostdlib -fno-builtin -ffreestanding \\",
            "\t\t-I$(abspath $(LIB_INCS)) \\",
            "\t\t-I$(abspath $(LIB_INCS))/../../ \\",
            "\t\t-T$(abspath $(LIB_LD)) $^ -o $@ \\",
            "\t\t-nostartfiles -lm -lgcc -static -specs=nano.specs \\",
            "\t\t|| { echo \"\\033[0;31mCOMPILE FAILED\\033[0m\"; exit 1; }",
            "\t@echo \"\\033[0;32m[COMPILE-ELF-OPT] Optimized ELF compilation completed!\\033[0m\"",
            "",
            "compile-croc-opt: $(COMPILE_ELF_OPT)",
            "",
            "compile: compile-croc-unopt compile-croc-opt",
            "\t@echo \"\\033[0;32m[COMPILE] =====================================================================================\\033[0m\"",
            "\t$(PRINT_OK)",
            "\t@echo \"\\033[0;32m[COMPILE] Compilation completed successfully!\\033[0m\"",
            "\t@echo \"\\033[0;32m[COMPILE] Reports located at $(PWD)/$(COMPILE_REPORT_PATH)/$(PROJ)_patmatch.rpt\\033[0m\"",
            "\t@echo \"\\033[0;32m[COMPILE] and $(PWD)/$(COMPILE_REPORT_PATH)/$(PROJ)_vec.rpt\\033[0m\"",
            "\t@echo \"\\033[0;32m[COMPILE] \\033[0m\"",
            "\t@echo \"\\033[0;32m[COMPILE] =====================================================================================\\033[0m\"",
            "",
            "clean-compile:",
            "\t@echo \"[CLEAN] Cleaning compilation outputs...\"",
            "\t@rm -rf $(realpath $(COMPILE_OUTPUT_PATH)) $(realpath $(COMPILE_REPORT_PATH))",
            "\t@echo \"[CLEAN] Compilation cleanup completed!\"",
            "",
        ]
        return '\n'.join(lines)
    
    def _generate_simulation_section_chipyard(self):
        """Generate the simulation section of the Makefile."""
        lines = [
            "## Simulation",
            "SIMULATION_PATH := ../../aps-chipyard/sims/verilator",
            "SIMULATION_REPORT_PATH_ROCKET := $(SIMULATION_PATH)/output/chipyard.harness.TestHarness.APSRocketConfig",
            "SIMULATION_REPORT_PATH := report/sim",
            "SIMULATION_REPORT_TRACE_UNOPT := report/sim/$(PROJ)_unopt.out",
            "SIMULATION_REPORT_TRACE_OPT := report/sim/$(PROJ)_opt.out",
            "",
            "sim-rocket-unopt: $(SIMULATION_REPORT_TRACE_UNOPT)",
            "",
            "$(SIMULATION_REPORT_TRACE_UNOPT): $(SYNTH_OUTPUT_JSON) $(COMPILE_ELF_UNOPT)",
            "\t@echo \"\\033[0;32m[SIM-UNOPT] Starting unoptimized simulation...\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM-UNOPT] Running RocketChip simulation...\\033[0m\"",
            "\t@cd $(SIMULATION_PATH) && $(MAKE) CONFIG=APSRocketConfig run-binary-debug \\",
            "\t\tBINARY=$(realpath $(COMPILE_ELF_UNOPT)) LOADMEM=1 || { \\",
            "\t\t\techo \"\\033[0;31m[SIM-UNOPT] SIM FAILED (UNOPT)!\\033[0m\"; \\",
            "\t\t\techo \"\\033[0;31m[SIM-UNOPT] Copying simulation results...\\033[0m\"; \\",
            "\t\t\tmkdir -p $(SIMULATION_REPORT_PATH); \\",
            "\t\t\tcp $(SIMULATION_REPORT_PATH_ROCKET)/$(PROJ)_unopt.* $(SIMULATION_REPORT_PATH); \\",
            "\t\t\texit 1; \\",
            "\t\t}",
            "\t@echo \"\\033[0;32m[SIM-UNOPT] Copying simulation results...\\033[0m\"",
            "\t@mkdir -p $(SIMULATION_REPORT_PATH)",
            "\t@cp $(SIMULATION_REPORT_PATH_ROCKET)/$(PROJ)_unopt.* $(SIMULATION_REPORT_PATH)",
            "\t@echo \"\\033[0;32m[SIM-UNOPT] Unoptimized simulation completed!\\033[0m\"",
            "",
            "sim-rocket-opt: $(SIMULATION_REPORT_TRACE_OPT)",
            "",
            "$(SIMULATION_REPORT_TRACE_OPT): $(SYNTH_OUTPUT_JSON) $(COMPILE_ELF_OPT)",
            "\t@echo \"\\033[0;32m[SIM-OPT] Starting optimized simulation...\\033[0m\"",
            "\t@cp $(SYNTH_OUTPUT_JSON) ../../aps-chipyard/aps_config.json",
            "\t@echo \"[SIM-OPT] Cleaning up previous simulation artifacts...\"",
            "\t@-rm -r ../../aps-chipyard/sims/verilator/generated-src/chipyard.harness.TestHarness.APSRocketConfig/",
            "\t@echo \"\\033[0;32m[SIM-OPT] Running RocketChip simulation...\\033[0m\"",
            "\t@-cd $(SIMULATION_PATH) && $(MAKE) CONFIG=APSRocketConfig run-binary-debug \\",
            "\t\tBINARY=$(realpath $(COMPILE_ELF_OPT)) LOADMEM=1 || { \\",
            "\t\t\techo \"\\033[0;31m[SIM-OPT] SIM FAILED (OPT)!\\033[0m\"; \\",
            "\t\t\techo \"\\033[0;31m[SIM-OPT] Copying simulation results...\\033[0m\"; \\",
            "\t\t\tmkdir -p $(SIMULATION_REPORT_PATH); \\",
            "\t\t\tcp $(SIMULATION_REPORT_PATH_ROCKET)/$(PROJ)_opt.* $(SIMULATION_REPORT_PATH); \\",
            "\t\t\texit 1; \\",
            "\t\t}",
            "\t@echo \"\\033[0;32m[SIM-OPT] Copying simulation results...\\033[0m\"",
            "\t@mkdir -p $(SIMULATION_REPORT_PATH)",
            "\t@cp $(SIMULATION_REPORT_PATH_ROCKET)/$(PROJ)_opt.* $(SIMULATION_REPORT_PATH)",
            "\t@echo \"\\033[0;32m[SIM-OPT] Optimized simulation completed!\\033[0m\"",
            "",
            "SIMULATION_REPORT_UNOPT_VIS = $(SIMULATION_REPORT_PATH)/$(PROJ)_unopt.html",
            "SIMULATION_REPORT_OPT_VIS = $(SIMULATION_REPORT_PATH)/$(PROJ)_opt.html",
            "SIMULATION_REPORT_COMBINED_VIS = $(SIMULATION_REPORT_PATH)/$(PROJ)_combined.html",
            "SIMULATION_REPORT_UNOPT = $(SIMULATION_REPORT_PATH)/$(PROJ)_unopt.json",
            "SIMULATION_REPORT_OPT = $(SIMULATION_REPORT_PATH)/$(PROJ)_opt.json",
            "SIMULATION_REPORT_CMP = $(SIMULATION_REPORT_PATH)/$(PROJ)_compare.rpt",
            "sim-rocket-report-unopt: $(SIMULATION_REPORT_UNOPT_VIS)",
            "sim-rocket-report-opt: $(SIMULATION_REPORT_OPT_VIS)",
            "sim-rocket-report-combined: $(SIMULATION_REPORT_COMBINED_VIS)",
            "",
            "$(SIMULATION_REPORT_UNOPT_VIS): $(SIMULATION_REPORT_TRACE_UNOPT)",
            "\t@python ../../scripts/analyze_trace.py $(realpath $(COMPILE_ELF_UNOPT)) $(realpath $(SIMULATION_REPORT_TRACE_UNOPT)) \\",
            "\t\t$(PWD)/$(SIMULATION_REPORT_UNOPT) chipyard",
            "\t@cp ../../scripts/analysis_template.html $(SIMULATION_REPORT_UNOPT_VIS)",
            "\t@sed -i \"s#analysis_output\\.json#$(notdir $(SIMULATION_REPORT_UNOPT))#g\" $(SIMULATION_REPORT_UNOPT_VIS)",
            "",
            "$(SIMULATION_REPORT_OPT_VIS): $(SIMULATION_REPORT_TRACE_OPT)",
            "\t@python ../../scripts/analyze_trace.py $(realpath $(COMPILE_ELF_OPT)) $(realpath $(SIMULATION_REPORT_TRACE_OPT)) \\",
            "\t\t$(PWD)/$(SIMULATION_REPORT_OPT) chipyard",
            "\t@cp ../../scripts/analysis_template.html $(SIMULATION_REPORT_OPT_VIS)",
            "\t@sed -i \"s#analysis_output\\.json#$(notdir $(SIMULATION_REPORT_OPT))#g\" $(SIMULATION_REPORT_OPT_VIS)",
            "",
            "PATMATCH_RPT_PATH = $(COMPILE_REPORT_PATH)/$(PROJ)_patmatch.rpt",
            "VEC_RPT_PATH = $(COMPILE_REPORT_PATH)/$(PROJ)_vec.rpt",
            "ASIC_RPT_PATH = report/asic/physical_implementation/07_RocketTile.final.rpt",
            "",
            "$(SIMULATION_REPORT_COMBINED_VIS): $(SIMULATION_REPORT_UNOPT_VIS) $(SIMULATION_REPORT_OPT_VIS)",
            "\t@echo \"\\033[0;32m[SIM-COMBINED] Generating combined analysis report...\\033[0m\"",
            "\t@cp ../../scripts/analysis_combined_template.html $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#ISAX_NAME#$(PROJ)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#UNOPT_JSON_FILE#$(SIMULATION_REPORT_UNOPT)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#OPT_JSON_FILE#$(SIMULATION_REPORT_OPT)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#SOURCE_FILE_PATH#$(C_FILE)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#CADL_FILE_PATH#$(CADL_FILE)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#UNOPT_LLIR_PATH#$(COMPILE_OUTPUT_LL_UNOPT)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#OPT_LLIR_PATH#$(COMPILE_OUTPUT_LL_OPT)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#VERILOG_SV_PATH#$(SYNTH_OUTPUT_SV)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#VERILOG_FIR_PATH#$(SYNTH_OUTPUT_FIR)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#SEMANTIC_JSON_PATH#$(SYNTH_OUTPUT_SEMANTIC)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#SYNTH_JSON_PATH#$(SYNTH_OUTPUT_JSON)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#PAT_MATCH_RPT_PATH#$(PATMATCH_RPT_PATH)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#VEC_MATCH_RPT_PATH#$(VEC_RPT_PATH)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#ASIC_RPT_PATH#$(ASIC_RPT_PATH)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@echo \"\\033[0;32m[SIM-COMBINED] Combined analysis report generated successfully!\\033[0m\"",
            "",
            "sim-rocket-compare-report: $(SIMULATION_REPORT_CMP)",
            "",
            "$(SIMULATION_REPORT_CMP): $(SIMULATION_REPORT_UNOPT_VIS) $(SIMULATION_REPORT_OPT_VIS)",
            "\t@echo \"======================================\" > $(SIMULATION_REPORT_CMP)",
            "\t@echo \"Performance Report\" >> $(SIMULATION_REPORT_CMP)",
            "\t@echo \"======================================\" >> $(SIMULATION_REPORT_CMP)",
            "\t@format_cycle() { \\",
            "\t\tjq -r \".functions.$(C_FUNC_EVAL).execution_cycles_total\" \"$$1\" | \\",
            "\t\tawk '{ printf \"%d\\n\", $$1 }'; \\",
            "\t}; \\",
            "\techo -n \"Baseline cycle count: \" >> $(SIMULATION_REPORT_CMP); \\",
            "\tformat_cycle \"$(SIMULATION_REPORT_UNOPT)\" >> $(SIMULATION_REPORT_CMP)",
            "\t@format_cycle() { \\",
            "\t\tjq -r \".functions.$(C_FUNC_EVAL).execution_cycles_total\" \"$$1\" | \\",
            "\t\tawk '{ printf \"%d\\n\", $$1 }'; \\",
            "\t}; \\",
            "\techo -n \"ISAX-enabled cycle count: \" >> $(SIMULATION_REPORT_CMP); \\",
            "\tformat_cycle \"$(SIMULATION_REPORT_OPT)\" >> $(SIMULATION_REPORT_CMP)",
            "\t@echo -n \"Speedup: \" >> $(SIMULATION_REPORT_CMP); \\",
            "\tB=`jq -r \".functions.$(C_FUNC_EVAL).execution_cycles_total\" \"$(SIMULATION_REPORT_UNOPT)\"`; \\",
            "\tI=`jq -r \".functions.$(C_FUNC_EVAL).execution_cycles_total\" \"$(SIMULATION_REPORT_OPT)\"`; \\",
            "\tS=`echo \"scale=4; $$B / $$I\" | bc`; \\",
            "\tprintf \"%.2f\" \"$$S\" >> $(SIMULATION_REPORT_CMP); \\",
            "\techo \"x\" >> $(SIMULATION_REPORT_CMP)",
            "",
            "sim-rocket-report: sim-rocket-report-unopt sim-rocket-report-opt sim-rocket-report-combined sim-rocket-compare-report",
            "\t@echo \"\\033[0;32m[SIM] =====================================================================================\\033[0m\"",
            "\t$(PRINT_OK)",
            "\t@echo \"\\033[0;32m[SIM] Simulation completed successfully!\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM] Reports located at:\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM]   - Combined report: $(abspath $(SIMULATION_REPORT_COMBINED_VIS))\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM]   - Optimized version: $(abspath $(SIMULATION_REPORT_OPT_VIS))\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM]   - Original version: $(abspath $(SIMULATION_REPORT_UNOPT_VIS))\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM]   - Text comparison: $(abspath $(SIMULATION_REPORT_CMP))\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM] \\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM] =====================================================================================\\033[0m\"",
            "",
            "sim: sim-rocket-unopt sim-rocket-opt sim-rocket-report",
            "",
            "clean-sim:",
            "\t@echo \"[CLEAN] Cleaning simulation outputs...\"",
            "\t@rm -rf $(realpath $(SIMULATION_REPORT_PATH))",
            "\t@echo \"[CLEAN] simulation cleanup completed!\"",
            "",
        ]
        return '\n'.join(lines)
    
    def _generate_simulation_section_croc(self):
        """Generate the CROC simulation section of the Makefile."""
        lines = [
            "## Simulation",
            "SIMULATION_REPORT_PATH := report/sim",
            "CROC_PATH := ../../aps-croc",
            "CROC_SW_PATH := $(CROC_PATH)/sw",
            "CROC_VERILATOR_PATH := $(CROC_PATH)/verilator/$(PROJ)",
            "CROC_BIN_PATH := $(CROC_PATH)/sw/bin",
            "SIMULATION_REPORT_TRACE_UNOPT := report/sim/$(PROJ)_unopt.out",
            "SIMULATION_REPORT_TRACE_OPT := report/sim/$(PROJ)_opt.out",
            "",
            "sim-croc-unopt: $(SIMULATION_REPORT_TRACE_UNOPT)",
            "",
            "$(SIMULATION_REPORT_PATH)/$(PROJ)_unopt.out: $(COMPILE_ELF_UNOPT)",
            "\t@echo \"\\033[0;32m[SIM-UNOPT] Starting unoptimized simulation...\\033[0m\"",
            "\t@riscv32-unknown-elf-objcopy --strip-debug -O verilog $(COMPILE_ELF_UNOPT) $(COMPILE_HEX_UNOPT)",
            "\t@echo \"\\033[0;32m[SIM-UNOPT] Running Croc simulation...\\033[0m\"",
            "\t@cd $(CROC_PATH) && $(MAKE) verilator ISAX_NAME=$(PROJ)_unopt SW_HEX=$(abspath $(COMPILE_HEX_UNOPT)) || { \\",
            "\t\techo \"\\033[0;31m[SIM-UNOPT] SIM FAILED (UNOPT)!\\033[0m\"; \\",
            "\t\techo \"\\033[0;31m[SIM-UNOPT] Copying simulation results...\\033[0m\"; \\",
            "\t\tmkdir -p $(SIMULATION_REPORT_PATH); \\",
            "\t\t@cp $(CROC_VERILATOR_PATH)_unopt/trace_rvfi.log $(SIMULATION_REPORT_PATH)/$(PROJ)_unopt.out \\",
            "\t\t@cp $(CROC_VERILATOR_PATH)_unopt/croc.vcd $(SIMULATION_REPORT_PATH)/$(PROJ)_unopt.vcd \\",
            "\t\texit 1; \\",
            "\t}",
            "\t@echo \"\\033[0;32m[SIM-UNOPT] Copying simulation results...\\033[0m\"",
            "\t@mkdir -p $(SIMULATION_REPORT_PATH)",
            "\t@cp $(CROC_VERILATOR_PATH)_unopt/trace_rvfi.log $(SIMULATION_REPORT_PATH)/$(PROJ)_unopt.out",
            "\t@cp $(CROC_VERILATOR_PATH)_unopt/croc.vcd $(SIMULATION_REPORT_PATH)/$(PROJ)_unopt.vcd",
            "\t@echo \"\\033[0;32m[SIM-UNOPT] Unoptimized simulation completed!\\033[0m\"",
            "",
            "sim-croc-opt: $(SIMULATION_REPORT_TRACE_OPT)",
            "",
            "$(SIMULATION_REPORT_PATH)/$(PROJ)_opt.out: $(COMPILE_ELF_OPT)",
            "\t@echo \"\\033[0;32m[SIM-OPT] Starting Optimized simulation...\\033[0m\"",
            "\t@riscv32-unknown-elf-objcopy --strip-debug -O verilog $(COMPILE_ELF_OPT) $(COMPILE_HEX_OPT)",
            "\t@echo \"\\033[0;32m[SIM-OPT] Running Croc simulation...\\033[0m\"",
            "\t@cd $(CROC_PATH) && $(MAKE) verilator ISAX_NAME=$(PROJ)_opt SW_HEX=$(abspath $(COMPILE_HEX_OPT)) || { \\",
            "\t\t@echo \"\\033[0;31m[SIM-OPT] SIM FAILED (UNOPT)!\\033[0m\"; \\",
            "\t\t@echo \"\\033[0;31m[SIM-OPT] Copying simulation results...\\033[0m\"; \\",
            "\t\t@mkdir -p $(SIMULATION_REPORT_PATH); \\",
            "\t\t@cp $(CROC_VERILATOR_PATH)_opt/trace_rvfi.log $(SIMULATION_REPORT_PATH)/$(PROJ)_opt.out \\",
            "\t\t@cp $(CROC_VERILATOR_PATH)_opt/croc.vcd $(SIMULATION_REPORT_PATH)/$(PROJ)_opt.vcd \\",
            "\t\texit 1; \\",
            "\t}",
            "\t@echo \"\\033[0;32m[SIM-OPT] Copying simulation results...\\033[0m\"",
            "\t@mkdir -p $(SIMULATION_REPORT_PATH)",
            "\t@cp $(CROC_VERILATOR_PATH)_opt/trace_rvfi.log $(SIMULATION_REPORT_PATH)/$(PROJ)_opt.out",
            "\t@cp $(CROC_VERILATOR_PATH)_opt/croc.vcd $(SIMULATION_REPORT_PATH)/$(PROJ)_opt.vcd",
            "\t@echo \"\\033[0;32m[SIM-OPT] Optimized simulation completed!\\033[0m\"",
            "",
            "SIMULATION_REPORT_UNOPT_VIS = $(SIMULATION_REPORT_PATH)/$(PROJ)_unopt.html",
            "SIMULATION_REPORT_OPT_VIS = $(SIMULATION_REPORT_PATH)/$(PROJ)_opt.html",
            "SIMULATION_REPORT_COMBINED_VIS = $(SIMULATION_REPORT_PATH)/$(PROJ)_combined.html",
            "SIMULATION_REPORT_UNOPT = $(SIMULATION_REPORT_PATH)/$(PROJ)_unopt.json",
            "SIMULATION_REPORT_OPT = $(SIMULATION_REPORT_PATH)/$(PROJ)_opt.json",
            "SIMULATION_REPORT_CMP = $(SIMULATION_REPORT_PATH)/$(PROJ)_compare.rpt",
            "sim-report-unopt: $(SIMULATION_REPORT_UNOPT_VIS)",
            "sim-report-opt: $(SIMULATION_REPORT_OPT_VIS)",
            "sim-report-combined: $(SIMULATION_REPORT_COMBINED_VIS)",
            "",
            "$(SIMULATION_REPORT_UNOPT_VIS): $(SIMULATION_REPORT_TRACE_UNOPT)",
            "\t@python ../../scripts/analyze_trace.py $(realpath $(COMPILE_ELF_UNOPT)) $(realpath $(SIMULATION_REPORT_TRACE_UNOPT)) \\",
            "\t\t$(PWD)/$(SIMULATION_REPORT_UNOPT) croc",
            "\t@cp ../../scripts/analysis_template.html $(SIMULATION_REPORT_UNOPT_VIS)",
            "\t@sed -i \"s#analysis_output\.json#$(notdir $(SIMULATION_REPORT_UNOPT))#g\" $(SIMULATION_REPORT_UNOPT_VIS)",
            "",
            "$(SIMULATION_REPORT_OPT_VIS): $(SIMULATION_REPORT_TRACE_OPT)",
            "\t@python ../../scripts/analyze_trace.py $(realpath $(COMPILE_ELF_OPT)) $(realpath $(SIMULATION_REPORT_TRACE_OPT)) \\",
            "\t\t$(PWD)/$(SIMULATION_REPORT_OPT) croc",
            "\t@cp ../../scripts/analysis_template.html $(SIMULATION_REPORT_OPT_VIS)",
            "\t@sed -i \"s#analysis_output\.json#$(notdir $(SIMULATION_REPORT_OPT))#g\" $(SIMULATION_REPORT_OPT_VIS)",
            "",
            "PATMATCH_RPT_PATH = $(COMPILE_REPORT_PATH)/$(PROJ)_patmatch.rpt",
            "VEC_RPT_PATH = $(COMPILE_REPORT_PATH)/$(PROJ)_vec.rpt",
            "ASIC_RPT_PATH = report/asic/physical_implementation/07_croc.final.rpt",
            "",
            "$(SIMULATION_REPORT_COMBINED_VIS): $(SIMULATION_REPORT_UNOPT_VIS) $(SIMULATION_REPORT_OPT_VIS)",
            "\t@echo \"\\033[0;32m[SIM-COMBINED] Generating combined analysis report...\\033[0m\"",
            "\t@cp ../../scripts/analysis_combined_template.html $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#ISAX_NAME#$(PROJ)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#UNOPT_JSON_FILE#$(SIMULATION_REPORT_UNOPT)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#OPT_JSON_FILE#$(SIMULATION_REPORT_OPT)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#SOURCE_FILE_PATH#$(C_FILE)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#CADL_FILE_PATH#$(CADL_FILE)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#UNOPT_LLIR_PATH#$(COMPILE_OUTPUT_LL_UNOPT)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#OPT_LLIR_PATH#$(COMPILE_OUTPUT_LL_OPT)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#VERILOG_SV_PATH#$(SYNTH_OUTPUT_SV)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#VERILOG_FIR_PATH#$(SYNTH_OUTPUT_FIR)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#SEMANTIC_JSON_PATH#$(SYNTH_OUTPUT_SEMANTIC)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#SYNTH_JSON_PATH#$(SYNTH_OUTPUT_JSON)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#PAT_MATCH_RPT_PATH#$(PATMATCH_RPT_PATH)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#VEC_MATCH_RPT_PATH#$(VEC_RPT_PATH)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@sed -i \"s#ASIC_RPT_PATH#$(ASIC_RPT_PATH)#g\" $(SIMULATION_REPORT_COMBINED_VIS)",
            "\t@echo \"\\033[0;32m[SIM-COMBINED] Combined analysis report generated successfully!\\033[0m\"",
            "",
            "sim-compare-report: $(SIMULATION_REPORT_CMP)",
            "",
            "$(SIMULATION_REPORT_CMP): $(SIMULATION_REPORT_UNOPT_VIS) $(SIMULATION_REPORT_OPT_VIS)",
            "\t@echo \"======================================\" > $(SIMULATION_REPORT_CMP)",
            "\t@echo \"Performance Report\" >> $(SIMULATION_REPORT_CMP)",
            "\t@echo \"======================================\" >> $(SIMULATION_REPORT_CMP)",
            "\t@format_cycle() { \\",
            "\t\tjq -r \".functions.$(C_FUNC_EVAL).execution_cycles_total\" \"$$1\" | \\",
            "\t\tawk '{ printf \"%d\\n\", $$1 }'; \\",
            "\t}; \\",
            "\techo -n \"Baseline cycle count: \" >> $(SIMULATION_REPORT_CMP); \\",
            "\tformat_cycle \"$(SIMULATION_REPORT_UNOPT)\" >> $(SIMULATION_REPORT_CMP)",
            "\t@format_cycle() { \\",
            "\t\tjq -r \".functions.$(C_FUNC_EVAL).execution_cycles_total\" \"$$1\" | \\",
            "\t\tawk '{ printf \"%d\\n\", $$1 }'; \\",
            "\t}; \\",
            "\techo -n \"ISAX-enabled cycle count: \" >> $(SIMULATION_REPORT_CMP); \\",
            "\tformat_cycle \"$(SIMULATION_REPORT_OPT)\" >> $(SIMULATION_REPORT_CMP)",
            "\t@echo -n \"Speedup: \" >> $(SIMULATION_REPORT_CMP); \\",
            "\tB=`jq -r \".functions.$(C_FUNC_EVAL).execution_cycles_total\" \"$(SIMULATION_REPORT_UNOPT)\"`; \\",
            "\tI=`jq -r \".functions.$(C_FUNC_EVAL).execution_cycles_total\" \"$(SIMULATION_REPORT_OPT)\"`; \\",
            "\tS=`echo \"scale=4; $$B / $$I\" | bc`; \\",
            "\tprintf \"%.2f\" \"$$S\" >> $(SIMULATION_REPORT_CMP); \\",
            "\techo \"x\" >> $(SIMULATION_REPORT_CMP)",
            "",
            "sim-report: sim-report-unopt sim-report-opt sim-report-combined sim-compare-report",
            "\t@echo \"\\033[0;32m[SIM] ===============================================================================\\033[0m\"",
            "\t$(PRINT_OK)",
            "\t@echo \"\\033[0;32m[SIM] CROC simulation completed successfully!\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM] Reports located at:\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM]   - Combined report: $(abspath $(SIMULATION_REPORT_COMBINED_VIS))\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM]   - Optimized version: $(abspath $(SIMULATION_REPORT_OPT_VIS))\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM]   - Original version:  $(abspath $(SIMULATION_REPORT_UNOPT_VIS))\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM]   - Text comparison:   $(abspath $(SIMULATION_REPORT_CMP))\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM] ===============================================================================\\033[0m\"",
            "",
            "sim: sim-croc-unopt sim-croc-opt sim-report",
            "",
            "clean-sim:",
            "\t@echo \"[CLEAN] Cleaning CROC simulation outputs...\"",
            "\t@rm -rf $(realpath $(SIMULATION_REPORT_PATH))",
            "\t@rm -f $(CROC_SW_PATH)/$(PROJ)_*.c $(CROC_SW_PATH)/$(PROJ)_*.S",
            "\t@rm -rf $(realpath $(CROC_VERILATOR_PATH)/*)",
            "\t@echo \"[CLEAN] CROC simulation cleanup completed!\"",
            "",
        ]
        return '\n'.join(lines)

    def _generate_asic_section_chipyard(self):
        lines = [
            "# ASIC",
            "ASIC_OUT_PATH := out/asic",
            "ASIC_REPORT_PATH := report/asic",
            "ASIC_PATH := ../../aps-chipyard/nextvlsi",
            "ASIC_NETLIST = $(ASIC_OUT_PATH)/netlist.v",
            "ASIC_DEF = $(ASIC_OUT_PATH)/RocketTile.def",
            "",
            "$(ASIC_NETLIST): $(SYNTH_OUTPUT_JSON)",
            "\t@mkdir -p $(ASIC_OUT_PATH)",
            "\t@mkdir -p $(ASIC_REPORT_PATH)",
            "\t@mkdir -p $(ASIC_REPORT_PATH)/logic_synthesis",
            "\t@echo \"\\033[0;32m[ASIC] Starting logic synthesis...\\033[0m\"",
            "\tcd $(ASIC_PATH) && make yosys ISAX_NAME=$(PROJ) APS_CONFIG=$(abspath $(SYNTH_OUTPUT_JSON)) || { \\",
            "\t\techo \"\\033[0;31m[ASIC] LOGIS SYNTHESIS FAILED (OPT)!\\033[0m\"; \\",
            "\t\techo \"\\033[0;31m[ASIC] Copying logs...\\033[0m\"; \\",
            "\t\tcp $(ASIC_PATH)/yosys/$(PROJ)/RocketTile.log $(ASIC_REPORT_PATH)/logic_synthesis/logic_synthesis.log \\",
            "\t\tcp $(ASIC_PATH)/yosys/$(PROJ)/reports/* $(ASIC_REPORT_PATH)/logic_synthesis \\",
            "\t\texit 1; \\",
            "\t}",
            "\t@cp $(ASIC_PATH)/yosys/$(PROJ)/out/RocketTile_yosys.v $(ASIC_OUT_PATH)/netlist.v",
            "\t@cp $(ASIC_PATH)/yosys/$(PROJ)/out/RocketTile_yosys_debug.v $(ASIC_OUT_PATH)/netlist_debug.v",
            "\t@cp $(ASIC_PATH)/yosys/$(PROJ)/RocketTile.log $(ASIC_REPORT_PATH)/logic_synthesis/logic_synthesis.log",
            "\t@cp $(ASIC_PATH)/yosys/$(PROJ)/reports/* $(ASIC_REPORT_PATH)/logic_synthesis",
            "\t@echo \"\\033[0;32m[ASIC] Logic synthesis completed!\\033[0m\"",
            "",
            "$(ASIC_DEF): $(ASIC_NETLIST) $(SYNTH_OUTPUT_JSON)",
            "\t@mkdir -p $(ASIC_OUT_PATH)",
            "\t@mkdir -p $(ASIC_REPORT_PATH)",
            "\t@mkdir -p $(ASIC_REPORT_PATH)/physical_implementation",
            "\t@echo \"\\033[0;32m[ASIC] Starting physical design...\\033[0m\"",
            "\tcd $(ASIC_PATH) && make openroad ISAX_NAME=$(PROJ) APS_CONFIG=$(abspath $(SYNTH_OUTPUT_JSON)) TARGET_PERIOD=$(ASIC_TARGET_PERIOD) || { \\",
            "\t\techo \"\\033[0;31m[ASIC] PHYSICAL IMPLEMENTATION FAILED (OPT)!\\033[0m\"; \\",
            "\t\techo \"\\033[0;31m[ASIC] Copying logs...\\033[0m\"; \\",
            "\t\tcp $(ASIC_PATH)/openroad/$(PROJ)/RocketTile.log $(ASIC_REPORT_PATH)/physical_implementation/physical_implementation.log \\",
            "\t\tcp $(ASIC_PATH)/openroad/$(PROJ)/reports/* $(ASIC_REPORT_PATH)/physical_implementation \\",
            "\t\texit 1; \\",
            "\t}",
            "\t@cp $(ASIC_PATH)/openroad/$(PROJ)/out/* $(ASIC_OUT_PATH)/",
            "\t@cp $(ASIC_PATH)/openroad/$(PROJ)/RocketTile.log $(ASIC_REPORT_PATH)/physical_implementation/physical_implementation.log",
            "\t@cp $(ASIC_PATH)/openroad/$(PROJ)/reports/* $(ASIC_REPORT_PATH)/physical_implementation",
            "\t@echo \"\\033[0;32m[ASIC] Physical design completed!\\033[0m\"",
            "",
            "asic: $(ASIC_NETLIST) $(ASIC_DEF)",
            "\t@echo \"\\033[0;32m[SIM] =====================================================================================\\033[0m\"",
            "\t$(PRINT_OK)",
            "\t@echo \"\\033[0;32m[SIM] ASIC implementation completed successfully!\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM] \\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM] =====================================================================================\\033[0m\"",
            "",
            "clean-asic:",
            "\t@echo \"[CLEAN] Cleaning asic outputs...\"",
            "\t@rm -rf $(realpath $(ASIC_OUT_PATH)) $(realpath $(ASIC_REPORT_PATH))",
            "\t@echo \"[CLEAN] asic cleanup completed!\""
            "",
        ]
        return '\n'.join(lines)
    
    def _generate_asic_section_croc(self):
        lines = [
            "# ASIC",
            "ASIC_OUT_PATH := out/asic",
            "ASIC_REPORT_PATH := report/asic",
            "ASIC_PATH := ../../aps-croc",
            "ASIC_NETLIST = $(ASIC_OUT_PATH)/netlist.v",
            "ASIC_DEF = $(ASIC_OUT_PATH)/croc.def",
            "",
            "$(ASIC_NETLIST): $(SYNTH_OUTPUT_JSON)",
            "\t@mkdir -p $(ASIC_OUT_PATH)",
            "\t@mkdir -p $(ASIC_REPORT_PATH)",
            "\t@mkdir -p $(ASIC_REPORT_PATH)/logic_synthesis",
            "\t@echo \"\\033[0;32m[ASIC] Starting logic synthesis...\\033[0m\"",
            "\tcd $(ASIC_PATH) && make yosys ISAX_NAME=$(PROJ) APS_CONFIG=$(abspath $(SYNTH_OUTPUT_JSON)) || { \\",
            "\t\techo \"\\033[0;31m[ASIC] LOGIS SYNTHESIS FAILED (OPT)!\\033[0m\"; \\",
            "\t\techo \"\\033[0;31m[ASIC] Copying logs...\\033[0m\"; \\",
            "\t\tcp $(ASIC_PATH)/yosys/$(PROJ)/croc_chip.log $(ASIC_REPORT_PATH)/logic_synthesis/logic_synthesis.log \\",
            "\t\tcp $(ASIC_PATH)/yosys/$(PROJ)/reports/* $(ASIC_REPORT_PATH)/logic_synthesis \\",
            "\t\texit 1; \\",
            "\t}",
            "\t@cp $(ASIC_PATH)/yosys/$(PROJ)/out/croc_chip_yosys.v $(ASIC_OUT_PATH)/netlist.v",
            "\t@cp $(ASIC_PATH)/yosys/$(PROJ)/out/croc_chip_yosys_debug.v $(ASIC_OUT_PATH)/netlist_debug.v",
            "\t@cp $(ASIC_PATH)/yosys/$(PROJ)/croc_chip.log $(ASIC_REPORT_PATH)/logic_synthesis/logic_synthesis.log",
            "\t@cp $(ASIC_PATH)/yosys/$(PROJ)/reports/* $(ASIC_REPORT_PATH)/logic_synthesis",
            "\t@echo \"\\033[0;32m[ASIC] Logic synthesis completed!\\033[0m\"",
            "",
            "$(ASIC_DEF): $(ASIC_NETLIST) $(SYNTH_OUTPUT_JSON)",
            "\t@mkdir -p $(ASIC_OUT_PATH)",
            "\t@mkdir -p $(ASIC_REPORT_PATH)",
            "\t@mkdir -p $(ASIC_REPORT_PATH)/physical_implementation",
            "\t@echo \"\\033[0;32m[ASIC] Starting physical design...\\033[0m\"",
            "\tcd $(ASIC_PATH) && make openroad ISAX_NAME=$(PROJ) APS_CONFIG=$(abspath $(SYNTH_OUTPUT_JSON)) TARGET_PERIOD=$(ASIC_TARGET_PERIOD) || { \\",
            "\t\techo \"\\033[0;31m[ASIC] PHYSICAL IMPLEMENTATION FAILED (OPT)!\\033[0m\"; \\",
            "\t\techo \"\\033[0;31m[ASIC] Copying logs...\\033[0m\"; \\",
            "\t\tcp $(ASIC_PATH)/openroad/$(PROJ)/croc.log $(ASIC_REPORT_PATH)/physical_implementation/physical_implementation.log \\",
            "\t\tcp $(ASIC_PATH)/openroad/$(PROJ)/reports/* $(ASIC_REPORT_PATH)/physical_implementation \\",
            "\t\texit 1; \\",
            "\t}",
            "\t@cp $(ASIC_PATH)/openroad/$(PROJ)/out/* $(ASIC_OUT_PATH)/",
            "\t@cp $(ASIC_PATH)/openroad/$(PROJ)/croc.log $(ASIC_REPORT_PATH)/physical_implementation/physical_implementation.log",
            "\t@cp $(ASIC_PATH)/openroad/$(PROJ)/reports/* $(ASIC_REPORT_PATH)/physical_implementation",
            "\t@echo \"\\033[0;32m[ASIC] Physical design completed!\\033[0m\"",
            "",
            "asic: $(ASIC_NETLIST) $(ASIC_DEF)",
            "\t@echo \"\\033[0;32m[SIM] =====================================================================================\\033[0m\"",
            "\t$(PRINT_OK)",
            "\t@echo \"\\033[0;32m[SIM] ASIC implementation completed successfully!\\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM] \\033[0m\"",
            "\t@echo \"\\033[0;32m[SIM] =====================================================================================\\033[0m\"",
            "",
            "clean-asic:",
            "\t@echo \"[CLEAN] Cleaning asic outputs...\"",
            "\t@rm -rf $(realpath $(ASIC_OUT_PATH)) $(realpath $(ASIC_REPORT_PATH))",
            "\t@echo \"[CLEAN] asic cleanup completed!\""
            "",
        ]
        return '\n'.join(lines)
    
    def _generate_footer(self):
        """Generate the footer section of the Makefile."""
        lines = [
            ".PHONY: clean-synth clean-compile clean-sim clean-asic clean all",
            "",
            "clean: clean-synth clean-compile clean-sim clean-asic",
            "",
        ]
        return '\n'.join(lines)
    
    def generate_folder(self):
        script_dir = Path(__file__).parent
        proj_name = self._get_param('general', 'proj', 'project')
        workspace_path = script_dir / 'workspace' / proj_name
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (workspace_path / 'cadl').mkdir(exist_ok=True)
        (workspace_path / 'csrc').mkdir(exist_ok=True)
        (workspace_path / 'out').mkdir(exist_ok=True)
        (workspace_path / 'report').mkdir(exist_ok=True)
        
        # Create blank files in cadl and csrc directories
        cadl_file = workspace_path / 'cadl' / self._get_param('general', 'cadl', 'design.cadl')
        c_file = workspace_path / 'csrc' / self._get_param('general', 'c_file', 'main.c')
        
        # Create empty files if they don't exist
        cadl_file.touch(exist_ok=True)
        c_file.touch(exist_ok=True)
        
        return workspace_path
        
    
    def generate_makefile(self, output_path=None):
        """Generate the complete Makefile."""
        script_dir = Path(__file__).parent
        if output_path is None:
            output_path = script_dir / "workspace" / self._get_param('general', 'proj', 'project') / "Makefile"
        
        header = [
            "# This file is automatically generated by APS Makefile Generator, do not modify!",
            "",
            "ifndef APS_ENV",
            '$(error APS_ENV environment variable is not defined. Please activate aps-env first. Run: pixi s -e aps)',
            "endif",
            "",
        ]
        
        # Select simulation section based on platform
        platform = self._get_param('general', 'platform', 'rocc')
        if platform == 'croc':
            compile_section = self._generate_compile_section_croc()
            simulation_section = self._generate_simulation_section_croc()
            asic_section = self._generate_asic_section_croc()
        elif platform == 'rocc':
            compile_section = self._generate_compile_section_chipyard()
            simulation_section = self._generate_simulation_section_chipyard()
            asic_section = self._generate_asic_section_chipyard()
        
        makefile_content = '\n'.join([
            '\n'.join(header),
            self._generate_variables_section(),
            self._generate_targets_section(),
            self._generate_synthesis_section(),
            compile_section,
            simulation_section,
            asic_section,
            self._generate_footer()
        ])
        
        try:
            with open(output_path, 'w') as file:
                file.write(makefile_content)
            print(f"Makefile successfully generated at: {output_path}")
            return True
        except IOError as e:
            print(f"Error writing Makefile: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Generate Makefile from YAML configuration")
    parser.add_argument("config", help="YAML configuration file in workspace/configs")
    
    args = parser.parse_args()
    
    try:
        generator = MakefileGenerator(args.config)
        proj_path = generator.generate_folder()
        generator.generate_makefile(proj_path / "Makefile")
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exception(e)
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())