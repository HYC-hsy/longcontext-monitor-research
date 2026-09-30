
# Find where Protocol constants are defined
import subprocess
result = subprocess.run(['grep', '-r', 'type Protocol', '/app', '--include=*.go'], 
                       capture_output=True, text=True, timeout=5)
print("=== Protocol type definitions ===")
print(result.stdout[:1000])

result2 = subprocess.run(['grep', '-r', 'const.*TTHeader.*Protocol', '/app', '--include=*.go'], 
                        capture_output=True, text=True, timeout=5)
print("\n=== TTHeader constants ===")
print(result2.stdout[:1000])
