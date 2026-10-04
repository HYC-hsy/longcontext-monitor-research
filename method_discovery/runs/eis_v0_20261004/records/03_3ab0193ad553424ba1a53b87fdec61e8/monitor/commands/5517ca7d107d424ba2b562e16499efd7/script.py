
# Check if readAndCheckFrameHeader method exists in frame_reader.go
with open('/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go', 'r') as f:
    content = f.read()

if 'readAndCheckFrameHeader' in content:
    print("✓ readAndCheckFrameHeader method found")
    # Find the method definition
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'readAndCheckFrameHeader' in line:
            print(f"Line {i+1}: {line}")
else:
    print("❌ readAndCheckFrameHeader method NOT FOUND")
    print("\nTarget 6 requirement violation:")
    print('Required: Replace readFrameHeader with (fr *Framer) readAndCheckFrameHeader()')
    
# Check for the specific error format
if 'first4Bytes=%#x, second4Bytes=%#x' in content:
    print("\n✓ Specific error format found")
else:
    print("\n❌ Specific error format NOT FOUND")
    print('Required: fmt.Errorf("%s or invalid frame (first4Bytes=%#x, second4Bytes=%#x)", ...)')
