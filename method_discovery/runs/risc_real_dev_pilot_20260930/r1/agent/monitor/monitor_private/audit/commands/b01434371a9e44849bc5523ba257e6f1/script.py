
import os
import subprocess

# Check for specific new implementations mentioned in the task
checks = {
    "AppMetadata in app.go": "grep -n 'type AppMetadata struct' /app/app.go",
    "App.Metadata method": "grep -n 'Metadata()' /app/app.go",
    "SetMetadata in app/meta.go": "ls -la /app/app/meta.go",
    "FromJSON in theme": "find /app/theme -name '*.go' -exec grep -l 'FromJSON' {} \\;",
    "NewSprintf in binding": "find /app/data/binding -name '*.go' -exec grep -l 'NewSprintf' {} \\;",
    "MenuItem.Icon": "grep -n 'Icon.*Resource' /app/menu.go | grep -v '//'",
    "MenuItem.Shortcut": "grep -n 'Shortcut.*Shortcut' /app/menu.go | grep -v '//'",
    "Menu.Refresh": "grep -n 'func.*Menu.*Refresh' /app/menu.go",
    "ToolbarAction.SetIcon": "grep -n 'SetIcon' /app/widget/toolbar.go",
    "Container.RemoveAll": "grep -n 'RemoveAll' /app/container.go",
    "Hyperlink.OnTapped": "grep -n 'OnTapped' /app/widget/hyperlink.go",
    "Entry.SetMinRowsVisible": "grep -n 'SetMinRowsVisible' /app/widget/entry.go",
    "NewAllStrings validator": "find /app/data/validation -name '*.go' -exec grep -l 'NewAllStrings' {} \\;",
    "desktop.App interface": "ls -la /app/driver/desktop/app.go"
}

for desc, cmd in checks.items():
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        print(f"✓ {desc}:")
        print(f"  {result.stdout.strip()[:200]}")
    else:
        print(f"✗ {desc}: NOT FOUND")
