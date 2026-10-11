
# Check if fyneApp implements Metadata()
import subprocess

result = subprocess.run(
    ['grep', '-A', '10', 'func.*Metadata', '/app/app/app.go'],
    capture_output=True, text=True
)
print("=== fyneApp Metadata() implementation ===")
print(result.stdout if result.stdout else "NOT FOUND")
