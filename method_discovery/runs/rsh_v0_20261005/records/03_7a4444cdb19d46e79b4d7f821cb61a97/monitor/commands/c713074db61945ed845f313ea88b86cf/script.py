
import subprocess
import json

print("=== COMPREHENSIVE FINAL VERIFICATION OF ALL 6 TARGETS ===\n")

# Target 5: Client Option Category System (most recent work)
print("TARGET 5: Client Option Category System")
print("-" * 50)

# 1. TailOption
result = subprocess.run("grep -n 'func TailOption' /app/client/option.go", shell=True, capture_output=True, text=True)
print(f"1. TailOption: {'✓ FOUND' if result.returncode == 0 else '✗ MISSING'}")
if result.returncode == 0:
    print(f"   {result.stdout.strip()}")

# 2. WithRecvTimeout in callopt/streamcall
result = subprocess.run("grep -n 'func WithRecvTimeout' /app/client/callopt/streamcall/*.go", shell=True, capture_output=True, text=True)
print(f"\n2. WithRecvTimeout: {'✓ FOUND' if result.returncode == 0 else '✗ MISSING'}")
if result.returncode == 0:
    print(f"   {result.stdout.strip()}")

# 3. Retry migration - check WithFailureRetry uses UnaryOptions
result = subprocess.run("grep -A 10 'func WithFailureRetry' /app/client/option.go | grep -E 'Unary|o\\.(Unary)?Options'", shell=True, capture_output=True, text=True)
print(f"\n3. Retry migration: {'✓ LIKELY' if 'Unary' in result.stdout else '? UNCLEAR'}")
print(f"   Check if uses UnaryOptions: {result.stdout[:200] if result.stdout else 'no match'}")

# 4. WithUnary*/WithStream* functions
result = subprocess.run("grep -n '^func WithUnary\\|^func WithStream\\|^func WithTTHeader' /app/client/option.go | wc -l", shell=True, capture_output=True, text=True)
count = result.stdout.strip()
print(f"\n4. Option functions: {count} functions found")

print("\n" + "=" * 50)
print("TARGET 6: gRPC Diagnostics Enhancement")
print("-" * 50)

# 1. Dump() method on conn_pool
result = subprocess.run("grep -n 'func.*Dump' /app/pkg/remote/trans/nphttp2/conn_pool.go", shell=True, capture_output=True, text=True)
print(f"1. Dump() method: {'✓ FOUND' if result.returncode == 0 else '✗ MISSING'}")
if result.returncode == 0:
    print(f"   {result.stdout.strip()}")
    # Check if panic-safe (has recover)
    result2 = subprocess.run("grep -A 20 'func.*Dump' /app/pkg/remote/trans/nphttp2/conn_pool.go | grep recover", shell=True, capture_output=True, text=True)
    print(f"   Panic-safe (has recover): {'✓ YES' if result2.returncode == 0 else '? UNKNOWN'}")

# 2. frame_reader hex dump
result = subprocess.run("grep -n 'readAndCheckFrameHeader' /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go", shell=True, capture_output=True, text=True)
print(f"\n2. readAndCheckFrameHeader: {'✓ FOUND' if result.returncode == 0 else '✗ MISSING'}")
if result.returncode == 0:
    # Check if has hex dump in error
    result2 = subprocess.run("grep -A 10 'readAndCheckFrameHeader' /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | grep -i 'hex\\|%#x\\|first4Bytes'", shell=True, capture_output=True, text=True)
    print(f"   Has hex dump in error: {'✓ YES' if result2.returncode == 0 else '? UNKNOWN'}")
    if result2.returncode == 0:
        print(f"   {result2.stdout.strip()[:150]}")

print("\n" + "=" * 50)
print("SUMMARY")
print("-" * 50)
print("Targets 1-4: Previously verified complete")
print("Target 5: Checking above...")
print("Target 6: Checking above...")
