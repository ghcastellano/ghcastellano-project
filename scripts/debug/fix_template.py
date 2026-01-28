
path = 'src/templates/admin_dashboard.html'
with open(path, 'r') as f:
    content = f.read()

# Look for the broken pattern and replace it, or just strip and append
# The broken pattern is roughly: "    }\n\n        {\n        % endblock %\n    }"

# Less risky: Find the last occurrence of "    }" before the garbage and clean up
# Or just find the malformed string
malformed = """
        {
        % endblock %
    }"""

if malformed.strip() in content or "{ % endblock % }" in content or "% endblock %" in content:
    print("Found malformed content. Fixing...")
    # Attempt 1: Replace exact malformed (might fail if whitespace differs)
    # content = content.replace(malformed, "{% endblock %}")
    
    # Attempt 2: Aggressive fix. We know it ends with garbage.
    # Find the last closing brace of the css/script
    # The file ends with style tag usually? No, it ends with that malformed block.
    
    lines = content.splitlines()
    # Remove last few lines if they look like the garbage
    while lines and ("% endblock %" in lines[-1] or lines[-1].strip() == "}" or lines[-1].strip() == "{"):
        print(f"Removing line: {lines[-1]}")
        lines.pop()
    
    # Append the correct block
    lines.append("{% endblock %}")
    
    new_content = "\n".join(lines)
    with open(path, 'w') as f:
        f.write(new_content)
    print("Fixed.")
else:
    print("Malformed pattern not found directly. Checking end of file...")
    print(f"Tail: {content[-50:]}")
    # Force append if missing
    if "{% endblock %}" not in content[-50:]:
         with open(path, 'a') as f:
             f.write("\n{% endblock %}")
         print("Appended missing endblock.")

