
import os

# Find actual workspace structure
workspace = "task/workspace"
if os.path.exists(workspace):
    # List all .go files
    go_files = []
    for root, dirs, files in os.walk(workspace):
        # Skip hidden and vendor directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'vendor']
        for f in files:
            if f.endswith('.go'):
                rel_path = os.path.relpath(os.path.join(root, f), workspace)
                go_files.append(rel_path)
    
    go_files.sort()
    print(f"Found {len(go_files)} Go files")
    print("\nKey files for targets:")
    
    target_files = [
        'app.go',
        'app/meta.go',
        'app/app.go',
        'menu.go',
        'container.go',
        'theme/json.go',
        'data/binding/sprintf.go',
        'data/validation/all.go',
        'widget/toolbar.go',
        'widget/hyperlink.go',
        'widget/entry.go',
        'driver/desktop/app.go'
    ]
    
    for tf in target_files:
        if tf in go_files:
            print(f"  ✓ {tf}")
        else:
            print(f"  ✗ {tf} NOT FOUND")
else:
    print("Workspace not found")
