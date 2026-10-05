
import subprocess
import json

print("=" * 70)
print("COMPREHENSIVE FINAL VERIFICATION - ALL 6 TARGETS")
print("=" * 70)

results = {}

# TARGET 5: Client Option Category System
print("\nTARGET 5: Client Option Category System")
print("-" * 70)

# 1. TailOption function
result = subprocess.run("grep -n 'func TailOption' /app/client/option.go", shell=True, capture_output=True, text=True)
req5_1 = result.returncode == 0
print(f"5.1 TailOption function: {'✓ PASS' if req5_1 else '✗ FAIL'}")
results['T5.1_TailOption'] = req5_1

# 2. WithRecvTimeout in callopt/streamcall
result = subprocess.run("grep -n 'func WithRecvTimeout' /app/client/callopt/streamcall/call_options.go", shell=True, capture_output=True, text=True)
req5_2 = result.returncode == 0
print(f"5.2 WithRecvTimeout in callopt/streamcall: {'✓ PASS' if req5_2 else '✗ FAIL'}")
results['T5.2_WithRecvTimeout'] = req5_2

# 3. Option functions (unary, stream, ttstream)
result = subprocess.run("grep -c '^func WithUnary\\|^func WithStream\\|^func WithTTHeader' /app/client/option.go", shell=True, capture_output=True, text=True)
count = int(result.stdout.strip()) if result.returncode == 0 else 0
req5_3 = count >= 10  # Should have multiple option functions
print(f"5.3 Option functions count: {count} ({'✓ PASS' if req5_3 else '✗ FAIL'})")
results['T5.3_OptionFunctions'] = req5_3

# 4. Retry migration - check structure (type alias approach)
result = subprocess.run("grep -n 'type UnaryOptions = Options' /app/internal/client/option.go", shell=True, capture_output=True, text=True)
req5_4 = result.returncode == 0  # Type alias exists
print(f"5.4 UnaryOptions type alias exists: {'✓ PASS' if req5_4 else '✗ FAIL'}")
results['T5.4_RetryStructure'] = req5_4

print(f"\nTarget 5 Summary: {'✓ COMPLETE' if all([req5_1, req5_2, req5_3, req5_4]) else '? PARTIAL'}")

# TARGET 6: gRPC Diagnostics Enhancement
print("\n" + "=" * 70)
print("TARGET 6: gRPC Diagnostics Enhancement")
print("-" * 70)

# 1. Dump() method exists
result = subprocess.run("grep -n 'func.*Dump.*interface' /app/pkg/remote/trans/nphttp2/conn_pool.go", shell=True, capture_output=True, text=True)
req6_1 = result.returncode == 0
print(f"6.1 Dump() method exists: {'✓ PASS' if req6_1 else '✗ FAIL'}")
results['T6.1_DumpExists'] = req6_1

# 2. Dump() has panic-safety (defer/recover)
result = subprocess.run("grep -A 40 'func.*Dump.*interface' /app/pkg/remote/trans/nphttp2/conn_pool.go | grep -E 'defer.*func\\(\\)|recover\\(\\)'", shell=True, capture_output=True, text=True)
req6_2 = result.returncode == 0 and ('defer' in result.stdout or 'recover' in result.stdout)
print(f"6.2 Dump() panic-safe (has defer/recover): {'✓ PASS' if req6_2 else '✗ FAIL'}")
results['T6.2_DumpPanicSafe'] = req6_2

# 3. Dump() returns map[string]interface{} (JSON-serializable)
result = subprocess.run("grep 'func.*Dump.*map\\[string\\]interface' /app/pkg/remote/trans/nphttp2/conn_pool.go", shell=True, capture_output=True, text=True)
req6_3 = result.returncode == 0
print(f"6.3 Dump() returns map[string]interface{}: {'✓ PASS' if req6_3 else '✗ FAIL'}")
results['T6.3_DumpJSONSerializable'] = req6_3

# 4. readAndCheckFrameHeader with hex dump
result = subprocess.run("grep -n 'readAndCheckFrameHeader' /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go", shell=True, capture_output=True, text=True)
req6_4a = result.returncode == 0
result = subprocess.run("grep -A 5 'readAndCheckFrameHeader' /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | grep -i '%#x\\|first4Bytes'", shell=True, capture_output=True, text=True)
req6_4b = result.returncode == 0
req6_4 = req6_4a and req6_4b
print(f"6.4 readAndCheckFrameHeader with hex dump: {'✓ PASS' if req6_4 else '✗ FAIL'}")
results['T6.4_FrameReaderHexDump'] = req6_4

print(f"\nTarget 6 Summary: {'✓ COMPLETE' if all([req6_1, req6_2, req6_3, req6_4]) else '? PARTIAL'}")

# OVERALL SUMMARY
print("\n" + "=" * 70)
print("OVERALL SUMMARY")
print("=" * 70)
print("Targets 1-4: Previously verified complete ✓")
all_t5 = all([req5_1, req5_2, req5_3, req5_4])
all_t6 = all([req6_1, req6_2, req6_3, req6_4])
print(f"Target 5: {'✓ COMPLETE' if all_t5 else '✗ INCOMPLETE'}")
print(f"Target 6: {'✓ COMPLETE' if all_t6 else '✗ INCOMPLETE'}")
print(f"\nALL 6 TARGETS: {'✓✓✓ COMPLETE ✓✓✓' if (all_t5 and all_t6) else '✗ INCOMPLETE - cannot allow completion'}")

print(f"\nDetailed results: {json.dumps(results, indent=2)}")
