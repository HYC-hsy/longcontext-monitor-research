
import subprocess

# Verify key implementations exist
checks = {
    "Target 1 - AppMetadata struct": "grep -n 'type AppMetadata struct' /app/app.go",
    "Target 1 - App.Metadata() method": "grep -n 'Metadata() AppMetadata' /app/app.go",
    "Target 1 - app/meta.go": "test -f /app/app/meta.go && echo 'EXISTS' || echo 'MISSING'",
    "Target 2 - FromJSON": "grep -n 'func FromJSON' /app/theme/json.go",
    "Target 3 - NewSprintf": "grep -n 'func NewSprintf' /app/data/binding/sprintf.go",
    "Target 3 - Set() with Sscanf": "grep -n 'fmt.Sscanf' /app/data/binding/sprintf.go",
    "Target 3 - URI in extractValue": "grep -A2 'case URI:' /app/data/binding/sprintf.go | head -4",
    "Target 4 - MenuItem.Icon": "grep -n 'Icon.*Resource' /app/menu.go | grep -v '//'",
    "Target 4 - MenuItem.Shortcut": "grep -n 'Shortcut.*Shortcut' /app/menu.go | grep -v '//'",
    "Target 4 - Menu.Refresh": "grep -n 'func.*Menu.*Refresh' /app/menu.go",
    "Target 5 - ToolbarAction.SetIcon": "grep -n 'func.*SetIcon' /app/widget/toolbar.go",
    "Target 6 - Container.RemoveAll": "grep -n 'func.*RemoveAll' /app/container.go",
    "Target 6 - Hyperlink.OnTapped": "grep -n 'OnTapped.*func' /app/widget/hyperlink.go",
    "Target 6 - Entry.SetMinRowsVisible": "grep -n 'func.*SetMinRowsVisible' /app/widget/entry.go",
    "Target 6 - validation.NewAllStrings": "find /app/data/validation -name '*.go' -exec grep -l 'func NewAllStrings' {} \\;",
    "Target 7 - desktop.App interface": "test -f /app/driver/desktop/app.go && echo 'EXISTS' || echo 'MISSING'",
}

for desc, cmd in checks.items():
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    status = "✓" if result.returncode == 0 and result.stdout.strip() else "✗"
    output = result.stdout.strip()[:100] if result.stdout.strip() else "NOT FOUND"
    print(f"{status} {desc}: {output}")
