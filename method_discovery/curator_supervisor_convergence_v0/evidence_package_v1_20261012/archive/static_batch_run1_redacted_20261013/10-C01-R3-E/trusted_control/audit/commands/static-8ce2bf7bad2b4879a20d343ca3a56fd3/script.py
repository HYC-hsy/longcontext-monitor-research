
# Search for SetMinRowsVisible in entry.go using the file_read content
import sys
sys.path.append('task')

# Read entry.go through file system if accessible
try:
    with open('task/workspace/widget/entry.go', 'r', encoding='utf-8') as f:
        entry_content = f.read()
        if 'SetMinRowsVisible' in entry_content:
            lines = entry_content.split('\n')
            for i, line in enumerate(lines):
                if 'SetMinRowsVisible' in line:
                    print(f"Found SetMinRowsVisible in entry.go at line {i+1}")
                    start = max(0, i-3)
                    end = min(len(lines), i+15)
                    for j in range(start, end):
                        print(f"{j+1:4d}: {lines[j]}")
                    break
        else:
            print("SetMinRowsVisible NOT found in entry.go")
except FileNotFoundError:
    print("Cannot access entry.go via filesystem")
except Exception as e:
    print(f"Error: {e}")
