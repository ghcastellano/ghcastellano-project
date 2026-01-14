import re
import os

filepath = 'src/templates/admin_dashboard.html'
print(f"Fixing {filepath}...")

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Regex to match the broken endblock pattern at the end of string
# Pattern seen: { \n % endblock % \n }
# We'll match anything looking like that at the end
pattern = re.compile(r'\s*\{\s*%\s*endblock\s*%\s*\}\s*$', re.DOTALL)

if pattern.search(content):
    print("Found broken pattern. Replacing...")
    new_content = pattern.sub('\n{% endblock %}\n', content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Fixed.")
else:
    print("Pattern not found. Appending anyway if not present.")
    if not content.strip().endswith('{% endblock %}'):
         with open(filepath, 'a', encoding='utf-8') as f:
            f.write('\n{% endblock %}\n')
         print("Appended {% endblock %}")
    else:
        print("Already correct.")
