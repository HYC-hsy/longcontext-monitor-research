
import subprocess

# Verify the 3 fixes
print("=== Verifying 3 fixes ===\n")

# 1. Check MainMenu.Refresh exists
result = subprocess.run(['grep', '-n', 'func.*MainMenu.*Refresh', '/app/menu.go'], 
                       capture_output=True, text=True)
print("1. MainMenu.Refresh():")
print(result.stdout if result.stdout else "NOT FOUND")

# 2. Check toolbar constructor return types
result = subprocess.run(['grep', '-n', 'func NewToolbar.*)', '/app/widget/toolbar.go'], 
                       capture_output=True, text=True)
print("\n2. Toolbar constructor signatures:")
print(result.stdout)

# 3. Check desktop.App interface methods
result = subprocess.run(['grep', '-A2', 'type App interface', '/app/driver/desktop/app.go'], 
                       capture_output=True, text=True)
print("\n3. desktop.App interface:")
print(result.stdout)
