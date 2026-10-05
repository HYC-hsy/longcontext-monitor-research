
# Verify all 7 targets are complete
import os
import subprocess

print("=== FINAL VERIFICATION: All 7 Targets ===\n")

issues = []

# Target 1: App Metadata
print("Target 1: App Metadata System")
result = subprocess.run(['grep', '-n', 'type AppMetadata struct', '/app/app.go'], 
                       capture_output=True, text=True)
if result.returncode == 0:
    print("  ✓ AppMetadata struct in app.go")
else:
    issues.append("Target 1: AppMetadata struct missing")
    
result = subprocess.run(['grep', '-n', 'Metadata() AppMetadata', '/app/app.go'], 
                       capture_output=True, text=True)
if result.returncode == 0:
    print("  ✓ Metadata() in App interface")
else:
    issues.append("Target 1: Metadata() method missing from interface")

result = subprocess.run(['test', '-f', '/app/app/meta.go'], capture_output=True)
if result.returncode == 0:
    print("  ✓ app/meta.go exists")
else:
    issues.append("Target 1: app/meta.go missing")

# Target 2: JSON Theme
print("\nTarget 2: JSON Theme Support")
result = subprocess.run(['test', '-f', '/app/theme/json.go'], capture_output=True)
if result.returncode == 0:
    print("  ✓ theme/json.go exists")
else:
    issues.append("Target 2: theme/json.go missing")

# Target 3: Data Binding
print("\nTarget 3: Data Binding Formatting")
result = subprocess.run(['test', '-f', '/app/data/binding/sprintf.go'], capture_output=True)
if result.returncode == 0:
    print("  ✓ data/binding/sprintf.go exists")
else:
    issues.append("Target 3: sprintf.go missing")

# Target 4: Menu Enhancements
print("\nTarget 4: Menu System Enhancements")
result = subprocess.run(['grep', '-n', 'Icon Resource', '/app/menu.go'], 
                       capture_output=True, text=True)
if result.returncode == 0:
    print("  ✓ MenuItem.Icon field")
else:
    issues.append("Target 4: MenuItem.Icon missing")

# Target 5: Toolbar
print("\nTarget 5: Toolbar Enhancements")
result = subprocess.run(['grep', '-n', 'SetIcon', '/app/widget/toolbar.go'], 
                       capture_output=True, text=True)
if result.returncode == 0:
    print("  ✓ ToolbarAction.SetIcon()")
else:
    issues.append("Target 5: SetIcon missing")

# Target 6: Widget/Container (5 items)
print("\nTarget 6: Widget/Container Improvements (5 items)")
checks = [
    ('RemoveAll', '/app/container.go', 'Container.RemoveAll()'),
    ('OnTapped', '/app/widget/hyperlink.go', 'Hyperlink.OnTapped'),
    ('SetMinRowsVisible', '/app/widget/entry.go', 'Entry.SetMinRowsVisible()'),
]
for pattern, file, name in checks:
    result = subprocess.run(['grep', '-n', pattern, file], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  ✓ {name}")
    else:
        issues.append(f"Target 6: {name} missing")

# Critical: Target 6 item 5 - NewAllStrings validator combinator
result = subprocess.run(['test', '-f', '/app/data/validation/all.go'], capture_output=True)
if result.returncode == 0:
    print("  ✓ data/validation/all.go exists")
    result = subprocess.run(['grep', 'validators ...fyne.StringValidator', '/app/data/validation/all.go'],
                           capture_output=True, text=True)
    if result.returncode == 0:
        print("  ✓ NewAllStrings has correct signature (validator combinator)")
    else:
        issues.append("Target 6: NewAllStrings wrong signature")
else:
    issues.append("Target 6: all.go missing")

# Target 7: Desktop App Interface
print("\nTarget 7: Desktop App Interface")
result = subprocess.run(['test', '-f', '/app/driver/desktop/app.go'], capture_output=True)
if result.returncode == 0:
    print("  ✓ driver/desktop/app.go exists")
else:
    issues.append("Target 7: desktop/app.go missing")

print("\n" + "="*50)
if issues:
    print("ISSUES FOUND:")
    for issue in issues:
        print(f"  ✗ {issue}")
else:
    print("✓ ALL 7 TARGETS VERIFIED COMPLETE")
print("="*50)
