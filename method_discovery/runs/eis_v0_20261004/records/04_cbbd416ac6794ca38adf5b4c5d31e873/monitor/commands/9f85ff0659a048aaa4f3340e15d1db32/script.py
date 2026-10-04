
import subprocess

# Test Target 1 compilation
result1 = subprocess.run(
    ['go', 'build', './pkg/streaming/'],
    cwd='/app',
    capture_output=True,
    text=True,
    timeout=30
)

print("=== Target 1: pkg/streaming/ ===")
print(f"Return code: {result1.returncode}")
if result1.returncode != 0:
    print(f"STDERR:\n{result1.stderr}")
else:
    print("✓ Compiles successfully")

# Test Target 2 compilation - cep
result2 = subprocess.run(
    ['go', 'build', './pkg/endpoint/cep/'],
    cwd='/app',
    capture_output=True,
    text=True,
    timeout=30
)

print("\n=== Target 2: pkg/endpoint/cep/ ===")
print(f"Return code: {result2.returncode}")
if result2.returncode != 0:
    print(f"STDERR:\n{result2.stderr}")
else:
    print("✓ Compiles successfully")

# Test Target 2 compilation - sep
result3 = subprocess.run(
    ['go', 'build', './pkg/endpoint/sep/'],
    cwd='/app',
    capture_output=True,
    text=True,
    timeout=30
)

print("\n=== Target 2: pkg/endpoint/sep/ ===")
print(f"Return code: {result3.returncode}")
if result3.returncode != 0:
    print(f"STDERR:\n{result3.stderr}")
else:
    print("✓ Compiles successfully")
