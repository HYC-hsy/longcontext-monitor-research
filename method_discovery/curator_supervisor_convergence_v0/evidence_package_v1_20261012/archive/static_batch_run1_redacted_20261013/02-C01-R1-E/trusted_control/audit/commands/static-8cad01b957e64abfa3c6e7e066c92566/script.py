
import os
import pathlib

# Search for SetMinRowsVisible method in entry.go
entry_path = pathlib.Path("task/workspace/widget/entry.go")
with open(entry_path, 'r', encoding='utf-8') as f:
    content = f.read()
    
# Search for SetMinRowsVisible
if 'SetMinRowsVisible' in content:
    print("✓ SetMinRowsVisible found in entry.go")
    # Find the method definition
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'SetMinRowsVisible' in line:
            # Print context around the method
            start = max(0, i - 2)
            end = min(len(lines), i + 15)
            print(f"\nContext (lines {start+1}-{end}):")
            for j in range(start, end):
                print(f"{j+1:4}: {lines[j]}")
            break
else:
    print("✗ SetMinRowsVisible NOT found in entry.go")

# Check if minRowsVisible field exists
if 'minRowsVisible' in content:
    print("\n✓ minRowsVisible field found")
else:
    print("\n✗ minRowsVisible field NOT found")
