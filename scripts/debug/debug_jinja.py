import re

def check_template(filename):
    with open(filename, 'r') as f:
        lines = f.readlines()

    stack = []
    print(f"Checking {filename}...")
    for i, line in enumerate(lines):
        line_num = i + 1
        # Find all block definitions
        blocks = re.findall(r'{%\s*block\s+(\w+)\s*%}', line)
        for block_name in blocks:
            print(f"Line {line_num}: Found start of block '{block_name}'")
            stack.append((block_name, line_num))
        
        # Find all endblock definitions
        endblocks = re.findall(r'{%\s*endblock\s*%}', line)
        for _ in endblocks:
            if not stack:
                print(f"ERROR: Line {line_num}: Found {{% endblock %}} but no block is open!")
                return
            
            last_block, last_line = stack.pop()
            print(f"Line {line_num}: Closed block '{last_block}' (opened at {last_line})")

    if stack:
        print("\n--- UNCLOSED BLOCKS ---")
        for block_name, line_num in stack:
            print(f"Block '{block_name}' opened at line {line_num} is never closed.")
    else:
        print("\nSUCCESS: All blocks balanced.")

check_template('src/templates/admin_dashboard.html')
