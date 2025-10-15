import re
import json
import sys
import subprocess
import argparse

def parse_elf_file(elf_file_path):
    functions = {}
    instructions = {}
    current_function = None

    try:
        result = subprocess.run(
            ["riscv32-unknown-elf-objdump", "-d", elf_file_path],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error running objdump: {e}")
        return None
    
    lines = result.stdout.splitlines()
    skip_section = False # Initialize skip flag
    for line in lines:
            # Match section headers (e.g., Disassembly of section .text:)
            section_match = re.match(r'Disassembly of section \.([^:]+):', line)
            if section_match:
                section_name = section_match.group(1)
                if section_name.startswith(('debug', 'misc')):
                    skip_section = True
                else:
                    skip_section = False
                current_function = None # Reset current function when a new section starts
                continue

            if skip_section:
                continue # Skip lines if we are in a discarded section

            # Match function headers (e.g., 10000000 <_start>:)
            func_match = re.match(r'([0-9a-f]+) <([^>]+)>:', line)
            if func_match:
                addr = int(func_match.group(1), 16)
                name = func_match.group(2)
                current_function = name
                functions[name] = {
                    'start_addr': addr,
                    'end_addr': addr, # Will be updated as instructions are added
                    'execution_count': 0,
                    'callees': {},
                    'instruction_pcs': [],
                    'execution_cycles_total': -1,
                    'execution_cycles_avg': -1,
                }
                continue

            # Match instructions (e.g., 10000000:	0002d197          	auipc	gt,0x2d)
            instr_match = re.match(r'\s*([0-9a-f]+):\s+([0-9a-f]+)\s+([a-z0-9.]+)\s*(.*)', line)
            if instr_match:
                pc = int(instr_match.group(1), 16)
                _ = instr_match.group(2)  # opcode, not used
                mnemonic = instr_match.group(3)
                operands = instr_match.group(4).strip()
                full_instruction = f"{mnemonic}\t{operands}"

                instructions[pc] = {
                    'pc': pc,
                    'instruction': full_instruction,
                    'execution_count': 0,
                    'total_cycles': 0,
                    'avg_cycles': 0,
                    'is_jal': False,
                    'target_function': None,
                    'function_name': current_function
                }

                if current_function:
                    functions[current_function]['instruction_pcs'].append(pc)
                    functions[current_function]['end_addr'] = pc # Update end address

                # Check for jal instruction
                if mnemonic == 'jal':
                    instructions[pc]['is_jal'] = True
                    # Extract target address from operands
                    target_match = re.search(r'([0-9a-f]+)\s+<([^>]+)>', operands)
                    if target_match:
                        target_addr = int(target_match.group(1), 16)
                        target_func_name = target_match.group(2)
                        instructions[pc]['target_function'] = target_func_name
                    else:
                        # Handle cases where target is not a direct function name (e.g., relative jump)
                        # For now, we'll just store the raw operand
                        instructions[pc]['target_function'] = operands.split()[0]

    # Refine function end addresses and map jal targets to function names
    sorted_function_addrs = sorted([(f['start_addr'], name) for name, f in functions.items()])
    for i, (start_addr, name) in enumerate(sorted_function_addrs):
        if i + 1 < len(sorted_function_addrs):
            next_start_addr = sorted_function_addrs[i+1][0]
            # The end address of a function is the address before the next function starts
            functions[name]['end_addr'] = next_start_addr - 4 # Assuming 4-byte instructions
        else:
            # For the last function, its end address is the last instruction's PC
            if functions[name]['instruction_pcs']:
                functions[name]['end_addr'] = max(functions[name]['instruction_pcs'])

    return functions, instructions

def process_trace_file_chipyard(trace_file_path, functions, instructions):
    last_global_cycle = None

    # Map PC to function name for quick lookup
    pc_to_function = {}
    for func_name, func_data in functions.items():
        for pc in func_data['instruction_pcs']:
            pc_to_function[pc] = func_name

    with open(trace_file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('C0:'):
                continue

            # Parse the new format: "C0:         19 [1] pc=[00010000] W[r10=00010000][1] R[r 0=00000000] R[r 0=00000000] inst=[00000517] auipc   a0, 0x0"
            try:
                # Extract cycle count - it's after "C0:" and before "["
                cycle_start = line.find('C0:') + 3
                cycle_end = line.find('[', cycle_start)
                if cycle_end == -1:
                    cycle_str = line[cycle_start:].strip().split()[0]
                else:
                    cycle_str = line[cycle_start:cycle_end].strip()
                
                cycle = int(cycle_str)

                # Extract PC - it's after "pc=[" and before "]"
                pc_start = line.find('pc=[') + 4
                pc_end = line.find(']', pc_start)
                pc_str = line[pc_start:pc_end]
                pc = int(pc_str, 16)

            except (ValueError, IndexError):
                continue

            if pc in instructions:
                instr_data = instructions[pc]
                instr_data['execution_count'] += 1

                if last_global_cycle is not None:
                    cycles_taken = cycle - last_global_cycle
                    instr_data['total_cycles'] += cycles_taken
                last_global_cycle = cycle

                # Update average cycles
                if instr_data['execution_count'] > 0:
                    instr_data['avg_cycles'] = instr_data['total_cycles'] / instr_data['execution_count']

                # Update function execution count
                func_name = pc_to_function.get(pc)
                if func_name and func_name in functions:
                    functions[func_name]['execution_count'] += 1

                # If it's a jal instruction, update callee count
                if instr_data['is_jal'] and instr_data['target_function']:
                    target_func = instr_data['target_function']
                    if func_name and func_name in functions and target_func in functions:
                        functions[func_name]['callees'][target_func] = functions[func_name]['callees'].get(target_func, 0) + 1
                        
    for func_name, func_data in functions.items():
        if len(func_data['instruction_pcs']) == 0:
            func_data['execution_count'] = 0
        else:
            instr_first_str = func_data['instruction_pcs'][0]
            instr_first = instructions[instr_first_str]
            func_data['execution_count'] = instr_first['execution_count']

    return functions, instructions

def process_trace_file_croc(trace_file_path, functions, instructions):
    last_global_cycle = None # Track the cycle of the previously executed instruction in the trace

    # Map PC to function name for quick lookup
    pc_to_function = {}
    for func_name, func_data in functions.items():
        for pc in func_data['instruction_pcs']:
            pc_to_function[pc] = func_name

    with open(trace_file_path, 'r') as f:
        # Skip header line
        next(f)
        for line in f:
            parts = line.strip().split()
            if len(parts) < 2:
                continue

            try:
                cycle = int(parts[0])
                pc = int(parts[1], 16)
            except ValueError:
                continue

            if pc in instructions:
                instr_data = instructions[pc]
                instr_data['execution_count'] += 1

                if last_global_cycle is not None:
                    cycles_taken = cycle - last_global_cycle
                    instr_data['total_cycles'] += cycles_taken
                # Update last_global_cycle for the next iteration
                last_global_cycle = cycle

                # Update average cycles
                if instr_data['execution_count'] > 0:
                    instr_data['avg_cycles'] = instr_data['total_cycles'] / instr_data['execution_count']

                # Update function execution count
                func_name = pc_to_function.get(pc)
                if func_name and func_name in functions:
                    functions[func_name]['execution_count'] += 1

                # If it's a jal instruction, update callee count
                if instr_data['is_jal'] and instr_data['target_function']:
                    target_func = instr_data['target_function']
                    if func_name and func_name in functions and target_func in functions:
                        functions[func_name]['callees'][target_func] = functions[func_name]['callees'].get(target_func, 0) + 1

    for func_name, func_data in functions.items():
        instr_first_str = func_data['instruction_pcs'][0]
        instr_first = instructions[instr_first_str]
        func_data['execution_count'] = instr_first['execution_count']

    return functions, instructions

def stat_isax_info(instructions):
    isax_info = {}
    for pc, instr in instructions.items():
        if instr['instruction'].startswith(".insn"):
            isax_info[pc] = instr
    return isax_info


def stat_function_info_helper(this_func_name, functions, instructions):
    exec_cycles_total = 0
    this_func = functions[this_func_name]
    # sum up it's content
    for instr_str in this_func['instruction_pcs']:
        instr = instructions[instr_str]
        exec_cycles_total += instr['total_cycles']
    # sum up it's callee's
    for callee, calltime in this_func['callees'].items():
        if functions[callee]['execution_cycles_avg'] == -1:
            functions, instructions = stat_function_info_helper(callee, functions, instructions)
        exec_cycles_total += functions[callee]['execution_cycles_avg'] * calltime
    # this gives execution_cycles_total, div execution_count gives execution_cycles_avg
    if functions[this_func_name]['execution_count'] > 0:
        functions[this_func_name]['execution_cycles_total'] = exec_cycles_total
        functions[this_func_name]['execution_cycles_avg'] = exec_cycles_total / functions[this_func_name]['execution_count']
    else:
        functions[this_func_name]['execution_cycles_total'] = 0
        functions[this_func_name]['execution_cycles_avg'] = 0
    # print(f'{this_func_name} ## {exec_cycles_total}')
    return functions, instructions

def stat_function_info(functions, instructions):
    for func_name, func_data in functions.items():
        if func_data['execution_cycles_total'] == -1:
            functions, instructions = stat_function_info_helper(func_name, functions, instructions)
    return functions, instructions

def main():
    parser = argparse.ArgumentParser(description='Analyze RISC-V trace files')
    parser.add_argument('elf_file', help='Path to the ELF file')
    parser.add_argument('trace_file', help='Path to the trace file')
    parser.add_argument('output_file', help='Path to the output report')
    parser.add_argument('backend_format', choices=['chipyard', 'croc'], 
                       help='Backend format (chipyard or croc)')
    
    args = parser.parse_args()
    
    elf_file = args.elf_file
    trace_file = args.trace_file
    backend_format = args.backend_format
    output_json_path = args.output_file

    print(f"Parsing ELF file: {elf_file}")
    functions, instructions = parse_elf_file(elf_file)
    print(f"Processing trace file: {trace_file} using {backend_format} backend format")
    
    if backend_format == 'chipyard':
        functions, instructions = process_trace_file_chipyard(trace_file, functions, instructions)
    elif backend_format == 'croc':
        functions, instructions = process_trace_file_croc(trace_file, functions, instructions)
    
    functions, instructions = stat_function_info(functions, instructions)
    isax_info = stat_isax_info(instructions)

    output_data = {
        "instructions": {},
        "functions": {},
        "isax": {}
    }

    for pc, data in instructions.items():
        output_data["instructions"][f"0x{pc:08x}"] = {
            "pc": f"0x{pc:08x}",
            "instruction": data["instruction"],
            "execution_count": data["execution_count"],
            "average_execution_cycles": data["avg_cycles"],
            "is_jal": data["is_jal"],
            "target_function": data["target_function"],
            "function_name": data["function_name"]
        }

    for name, data in functions.items():
        callees_cycle_data = {}
        for callee, calltime in data["callees"].items():
            callees_cycle_data[callee] = calltime * functions[callee]['execution_cycles_avg']

        output_data["functions"][name] = {
            "function_name": name,
            "execution_count": data['execution_count'],
            "callees_total": data["callees"], # sum up on every execution
            "callees_cycle_total": callees_cycle_data, # sum up on every execution
            # "instruction_pcs": [f"0x{pc:08x}" for pc in data["instruction_pcs"]],
            "execution_cycles_total": data["execution_cycles_total"],
            "execution_cycles_avg": data["execution_cycles_avg"],
        }

    for pc, data in isax_info.items():
        output_data["isax"][f"0x{pc:08x}"] = {
            "pc": f"0x{pc:08x}",
            "instruction": data["instruction"],
            "execution_count": data["execution_count"],
            "average_execution_cycles": data["avg_cycles"],
        }

    with open(output_json_path, 'w') as f:
        json.dump(output_data, f, indent=4)
    print(f"Analysis complete. Output saved to {output_json_path}")

if __name__ == "__main__":
    main()
