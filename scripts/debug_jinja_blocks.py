import re
import sys

def debug_template(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()

    stack = []
    block_regex = re.compile(r'{%\s*block\s+(\w+)\s*%}')
    endblock_regex = re.compile(r'{%\s*endblock\s*(?:\w+)?\s*%}')

    print(f"Analyzing {filepath}...")
    for i, line in enumerate(lines):
        line_num = i + 1
        
        # Find all blocks in line
        for match in block_regex.finditer(line):
            block_name = match.group(1)
            stack.append((line_num, block_name))
            print(f"Line {line_num}: Opened block '{block_name}'")

        # Find all endblocks in line
        for match in endblock_regex.finditer(line):
            if not stack:
                print(f"Line {line_num}: ❌ Unexpected 'endblock' (stack empty)")
            else:
                start_line, name = stack.pop()
                print(f"Line {line_num}: Closed block '{name}' (start: {start_line})")

    if stack:
        print("\n❌ Unclosed blocks found:")
        for line_num, name in stack:
            print(f"  - Block '{name}' started at line {line_num}")
            print(f"    Context: {lines[line_num-1].strip()}")
    else:
        print("\n✅ All blocks balanced.")

if __name__ == "__main__":
    debug_template("src/templates/admin_dashboard.html")
