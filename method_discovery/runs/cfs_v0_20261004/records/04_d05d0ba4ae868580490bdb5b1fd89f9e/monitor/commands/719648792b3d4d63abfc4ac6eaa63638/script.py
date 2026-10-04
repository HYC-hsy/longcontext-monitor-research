
# Search for the readAndCheckFrameHeader implementation
import subprocess

result = subprocess.run(
    ['grep', '-A', '30', 'func (fr \*Framer) readAndCheckFrameHeader', 
     '/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go'],
    capture_output=True,
    text=True
)

print("readAndCheckFrameHeader implementation:")
print("="*80)
print(result.stdout)

# Also check for hex formatting
result2 = subprocess.run(
    ['grep', '-n', '%#x\\|0x%x\\|%x', 
     '/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go'],
    capture_output=True,
    text=True
)

print("\n" + "="*80)
print("Hex format occurrences:")
print("="*80)
print(result2.stdout if result2.stdout else "No hex format found")
