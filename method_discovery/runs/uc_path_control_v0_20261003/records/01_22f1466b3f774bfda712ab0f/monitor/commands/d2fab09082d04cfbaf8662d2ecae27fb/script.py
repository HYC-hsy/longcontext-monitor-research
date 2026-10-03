
import subprocess
# Check for MainMenu.Refresh
result = subprocess.run(
    ['grep', '-n', 'func.*MainMenu.*Refresh', '/app/menu.go'],
    capture_output=True,
    text=True
)
print("MainMenu.Refresh:")
print(result.stdout if result.stdout else "Not found")
print()

# Check toolbar constructor signatures
result2 = subprocess.run(
    ['grep', '-n', 'func NewToolbar', '/app/widget/toolbar.go'],
    capture_output=True,
    text=True
)
print("Toolbar constructors:")
print(result2.stdout)
