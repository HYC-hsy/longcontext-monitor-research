
# Search for SetMinRowsVisible in entry.go using task workspace path
import os
workspace = "task/workspace"

entry_path = os.path.join(workspace, "widget", "entry.go")
if os.path.exists(entry_path):
    with open(entry_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for minRowsVisible field
    if 'minRowsVisible int' in content:
        print("✓ minRowsVisible field EXISTS in Entry struct")
    else:
        print("✗ minRowsVisible field NOT FOUND")
    
    # Check for SetMinRowsVisible method
    if 'func (e *Entry) SetMinRowsVisible' in content:
        print("✓ SetMinRowsVisible method EXISTS")
        # Find and display it
        start = content.find('func (e *Entry) SetMinRowsVisible')
        end = content.find('\n}', start) + 2
        print(content[start:end])
    else:
        print("✗ SetMinRowsVisible method NOT FOUND")
else:
    print(f"Entry file not found at {entry_path}")
