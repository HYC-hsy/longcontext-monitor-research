
import re

# Read the entire entry.go file
with open('task/workspace/widget/entry.go', 'r', encoding='utf-8') as f:
    content = f.read()

# Find SetMinRowsVisible method
set_min_pattern = r'func\s+\([^)]+\)\s+SetMinRowsVisible[^{]*\{[^}]*\}'
matches = re.finditer(set_min_pattern, content, re.MULTILINE | re.DOTALL)
for match in matches:
    print("=== SetMinRowsVisible method ===")
    print(match.group(0)[:500])
    print()

# Find MinSize method (first 1000 chars)
minsize_pattern = r'func\s+\([^)]+\)\s+MinSize\([^{]*\{.*?(?=\nfunc\s|\Z)'
matches = re.finditer(minsize_pattern, content, re.MULTILINE | re.DOTALL)
for match in matches:
    text = match.group(0)
    print("=== MinSize method (first 1000 chars) ===")
    print(text[:1000])
    print()
    if len(text) > 1000:
        print("... (truncated)")
