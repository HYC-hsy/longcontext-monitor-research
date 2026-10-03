
import subprocess
result = subprocess.run(
    ['grep', '-n', 'func.*Refresh', '/app/menu.go'],
    capture_output=True,
    text=True
)
print(result.stdout)
