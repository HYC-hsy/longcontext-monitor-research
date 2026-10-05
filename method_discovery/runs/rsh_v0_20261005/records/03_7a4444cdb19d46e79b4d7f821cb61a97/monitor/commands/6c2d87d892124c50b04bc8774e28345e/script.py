
import subprocess

print("=== DETAILED TARGET 6 FRAME_READER VERIFICATION ===\n")

# Check the actual readAndCheckFrameHeader implementation
result = subprocess.run(
    "grep -A 15 'func.*readAndCheckFrameHeader' /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go",
    shell=True, capture_output=True, text=True
)

print("readAndCheckFrameHeader implementation:")
print(result.stdout if result.stdout else "NOT FOUND")

print("\n" + "="*70)
print("SEARCHING FOR HEX FORMATTING:")
result = subprocess.run(
    "grep -n 'ErrFrameTooLarge\\|invalid frame\\|first4Bytes\\|second4Bytes\\|%#x' /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go",
    shell=True, capture_output=True, text=True
)
print(result.stdout if result.stdout else "NO HEX FORMATTING FOUND")

# Original task requirement
print("\n" + "="*70)
print("ORIGINAL TASK REQUIREMENT (Target 6.2):")
print('When frame size exceeds maxReadSize, return error containing:')
print('- http2.ErrFrameTooLarge text')
print('- "invalid frame" text')  
print('- Hex-formatted first and second 4 bytes:')
print('  fmt.Errorf("%s or invalid frame (first4Bytes=%#x, second4Bytes=%#x)", ..., buf[:4], buf[4:8])')
