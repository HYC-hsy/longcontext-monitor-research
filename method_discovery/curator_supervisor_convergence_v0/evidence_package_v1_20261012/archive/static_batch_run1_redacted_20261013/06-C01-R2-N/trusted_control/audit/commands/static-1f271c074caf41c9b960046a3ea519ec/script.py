
import os

# Check for SetMinRowsVisible in entry.go
print("=" * 80)
print("CHECKING Entry.SetMinRowsVisible METHOD")
print("=" * 80)

# Read the file content using file_read results
entry_content = open('task/workspace/widget/entry.go', 'r', encoding='utf-8').read()

if 'func (e *Entry) SetMinRowsVisible' in entry_content:
    print("✓ SetMinRowsVisible method FOUND")
    # Find and show it
    lines = entry_content.split('\n')
    for i, line in enumerate(lines):
        if 'SetMinRowsVisible' in line:
            start = max(0, i-2)
            end = min(len(lines), i+8)
            for j in range(start, end):
                print(f"{j+1}: {lines[j]}")
            break
else:
    print("❌ SetMinRowsVisible method NOT FOUND")
    print("   Only the minRowsVisible field exists (line 69), but no public method")

print("\n" + "=" * 80)
print("CHECKING NewAllStrings VALIDATOR")
print("=" * 80)

# Check for NewAllStrings in data/validation/
validation_path = 'task/workspace/data/validation'
if os.path.exists(validation_path):
    files = os.listdir(validation_path)
    print(f"Files in data/validation/: {files}")
    
    # Check for all.go
    all_go_path = os.path.join(validation_path, 'all.go')
    if os.path.exists(all_go_path):
        print("✓ all.go exists")
        with open(all_go_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'NewAllStrings' in content:
                print("✓ NewAllStrings FOUND in all.go")
            else:
                print("❌ NewAllStrings NOT FOUND in all.go")
    else:
        print("❌ all.go does NOT exist")
else:
    print("❌ data/validation directory does NOT exist")

print("\n" + "=" * 80)
print("CHECKING desktop.App INTERFACE")
print("=" * 80)

# Check for desktop.App interface
desktop_path = 'task/workspace/driver/desktop'
if os.path.exists(desktop_path):
    files = os.listdir(desktop_path)
    print(f"Files in driver/desktop/: {files}")
    
    app_go_path = os.path.join(desktop_path, 'app.go')
    if os.path.exists(app_go_path):
        print("✓ app.go exists")
        with open(app_go_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'type App interface' in content:
                print("✓ desktop.App interface FOUND")
                # Show the interface
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'type App interface' in line:
                        start = i
                        end = min(len(lines), i+15)
                        for j in range(start, end):
                            print(f"{j+1}: {lines[j]}")
                            if '}' in lines[j] and j > i:
                                break
                        break
            else:
                print("❌ desktop.App interface NOT FOUND in app.go")
    else:
        print("❌ app.go does NOT exist in driver/desktop/")
else:
    print("❌ driver/desktop directory does NOT exist")
