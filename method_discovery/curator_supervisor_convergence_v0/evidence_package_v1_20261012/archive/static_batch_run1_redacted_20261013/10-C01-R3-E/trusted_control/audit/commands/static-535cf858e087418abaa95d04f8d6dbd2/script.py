
# Search for SetMinRowsVisible in the file content using grep-like search
import re

def search_in_file(filepath, pattern):
    """Search for pattern in file and return matches with context"""
    try:
        # Using file_read through the task workspace mapping
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
            matches = []
            for i, line in enumerate(lines):
                if pattern in line:
                    # Get context
                    start = max(0, i-3)
                    end = min(len(lines), i+12)
                    context = '\n'.join([f"{j+1:4d}: {lines[j]}" for j in range(start, end)])
                    matches.append({
                        'line_num': i+1,
                        'line': line,
                        'context': context
                    })
            return matches
    except Exception as e:
        return None

# Check for SetMinRowsVisible in entry.go
print("=" * 70)
print("Searching for SetMinRowsVisible in entry.go:")
print("=" * 70)
entry_matches = search_in_file('task/workspace/widget/entry.go', 'SetMinRowsVisible')
if entry_matches:
    for m in entry_matches:
        print(f"\nFound at line {m['line_num']}:")
        print(m['context'])
else:
    print("NOT FOUND in entry.go")

print("\n" + "=" * 70)
print("Searching for SetMinRowsVisible in select.go:")
print("=" * 70)
select_matches = search_in_file('task/workspace/widget/select.go', 'SetMinRowsVisible')
if select_matches:
    for m in select_matches:
        print(f"\nFound at line {m['line_num']}:")
        print(m['context'])
else:
    print("NOT FOUND in select.go")
