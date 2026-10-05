
import subprocess

print("=" * 70)
print("COMPREHENSIVE FINAL VERIFICATION - ALL 6 TARGETS")
print("=" * 70)

# TARGET 5: Client Option Category System
print("\nTARGET 5: Client Option Category System")
print("-" * 70)

# 1. TailOption function
result = subprocess.run("grep -n 'func TailOption' /app/client/option.go", shell=True, capture_output=True, text=True)
req5_1 = result.returncode == 0
print(f"5.1 TailOption function: {'PASS' if req5_1 else 'FAIL'} - {result.returncode}")

# 2. WithRecvTimeout in callopt/streamcall
result = subprocess.run("grep -n 'func WithRecvTimeout' /app/client/callopt/streamcall/call_options.go", shell=True, capture_output=True, text=True)
req5_2 = result.returncode == 0
print(f"5.2 WithRecvTimeout: {'PASS' if req5_2 else 'FAIL'}")

# 3. Option functions count
result = subprocess.run("grep -c '^func WithUnary\\|^func WithStream\\|^func WithTTHeader' /app/client/option.go", shell=True, capture_output=True, text=True)
count = int(result.stdout.strip()) if result.returncode == 0 else 0
req5_3 = count >= 10
print(f"5.3 Option functions: {count} found ({'PASS' if req5_3 else 'FAIL'})")

# 4. Type aliases
result = subprocess.run("grep -n 'type UnaryOptions = Options' /app/internal/client/option.go", shell=True, capture_output=True, text=True)
req5_4 = result.returncode == 0
print(f"5.4 UnaryOptions type alias: {'PASS' if req5_4 else 'FAIL'}")

print(f"\nTarget 5: {'COMPLETE' if all([req5_1, req5_2, req5_3, req5_4]) else 'INCOMPLETE'}")

# TARGET 6: gRPC Diagnostics
print("\n" + "=" * 70)
print("TARGET 6: gRPC Diagnostics Enhancement")
print("-" * 70)

# 1. Dump() exists
result = subprocess.run("grep -n 'func.*Dump' /app/pkg/remote/trans/nphttp2/conn_pool.go", shell=True, capture_output=True, text=True)
req6_1 = result.returncode == 0
print(f"6.1 Dump() method: {'PASS' if req6_1 else 'FAIL'}")

# 2. Dump() panic-safe
result = subprocess.run("grep -A 40 'func.*Dump' /app/pkg/remote/trans/nphttp2/conn_pool.go | grep -E 'defer.*func|recover'", shell=True, capture_output=True, text=True)
has_defer = 'defer' in result.stdout.lower()
has_recover = 'recover' in result.stdout.lower()
req6_2 = result.returncode == 0 and (has_defer or has_recover)
print(f"6.2 Dump() panic-safe: {'PASS' if req6_2 else 'FAIL'} (defer={has_defer}, recover={has_recover})")

# 3. Dump() returns map
result = subprocess.run("grep 'func.*Dump.*map' /app/pkg/remote/trans/nphttp2/conn_pool.go", shell=True, capture_output=True, text=True)
req6_3 = result.returncode == 0 and 'interface' in result.stdout
print(f"6.3 Dump() returns map interface: {'PASS' if req6_3 else 'FAIL'}")

# 4. readAndCheckFrameHeader with hex
result = subprocess.run("grep -n 'readAndCheckFrameHeader' /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go", shell=True, capture_output=True, text=True)
exists = result.returncode == 0
result2 = subprocess.run("grep -A 5 'readAndCheckFrameHeader' /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | grep '%#x'", shell=True, capture_output=True, text=True)
has_hex = result2.returncode == 0
req6_4 = exists and has_hex
print(f"6.4 frame_reader hex dump: {'PASS' if req6_4 else 'FAIL'} (exists={exists}, hex={has_hex})")

print(f"\nTarget 6: {'COMPLETE' if all([req6_1, req6_2, req6_3, req6_4]) else 'INCOMPLETE'}")

# SUMMARY
print("\n" + "=" * 70)
print("FINAL SUMMARY")
print("=" * 70)
print("Targets 1-4: Previously verified complete")
all_t5 = all([req5_1, req5_2, req5_3, req5_4])
all_t6 = all([req6_1, req6_2, req6_3, req6_4])
print(f"Target 5: {'COMPLETE' if all_t5 else 'INCOMPLETE'}")
print(f"Target 6: {'COMPLETE' if all_t6 else 'INCOMPLETE'}")
print(f"\nALL 6 TARGETS: {'ALL COMPLETE' if (all_t5 and all_t6) else 'INCOMPLETE'}")
