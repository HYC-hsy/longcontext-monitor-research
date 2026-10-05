
import subprocess

print("=== FINAL ROOT COMPLETION VERIFICATION ===\n")

# My turn 206 verification found Target 6 frame_reader hex dump MISSING
# Let me re-verify now that agent claims complete

print("1. Target 6 frame_reader hex dump:")
result = subprocess.run(
    "grep -A 5 'if fh.Length > fr.maxReadSize' /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go",
    shell=True, capture_output=True, text=True
)
print(result.stdout if result.stdout else "NOT FOUND")

# Check if the hex formatting is present
has_hex = '%#x' in result.stdout and 'first4Bytes' in result.stdout and 'second4Bytes' in result.stdout
has_invalid_frame = 'invalid frame' in result.stdout
has_err_too_large = 'ErrFrameTooLarge' in result.stdout or 'FrameTooLarge' in result.stdout

print(f"\nHas hex formatting (%#x): {has_hex}")
print(f"Has 'invalid frame': {has_invalid_frame}")
print(f"Has ErrFrameTooLarge: {has_err_too_large}")

# Verify Dump() panic-safety (my intervention was implemented)
print("\n2. Dump() panic-safety:")
result = subprocess.run(
    "grep -A 5 'func.*Dump.*interface' /app/pkg/remote/trans/nphttp2/conn_pool.go | grep -E 'defer|recover'",
    shell=True, capture_output=True, text=True
)
has_panic_safe = 'defer' in result.stdout and 'recover' in result.stdout
print(f"Has defer/recover: {has_panic_safe}")
print(result.stdout[:200] if result.stdout else "NO PANIC SAFETY")

# Build status
print("\n3. Build status:")
result = subprocess.run("cd /app && go build ./... 2>&1 | head -5", shell=True, capture_output=True, text=True)
build_success = result.returncode == 0 and not result.stdout.strip()
print(f"Build: {'SUCCESS' if build_success else 'FAILED'}")
if not build_success:
    print(result.stdout[:300])

# Summary
print("\n" + "="*70)
print("COMPLETION ASSESSMENT:")
print(f"- Target 6.2 frame_reader hex dump: {'PASS' if (has_hex and has_invalid_frame and has_err_too_large) else 'FAIL'}")
print(f"- Target 6.1 Dump() panic-safe: {'PASS' if has_panic_safe else 'FAIL'}")
print(f"- Build: {'PASS' if build_success else 'FAIL'}")
print(f"\nREADY FOR COMPLETION: {'YES' if all([has_hex, has_invalid_frame, has_err_too_large, has_panic_safe, build_success]) else 'NO'}")
