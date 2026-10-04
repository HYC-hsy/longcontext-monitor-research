
# More thorough check of Target 4 and 6

# TARGET 4: Check thrift_data.go for Marshal/Unmarshal functions
import os

print("TARGET 4: Detailed Thrift Codec Check")
print("="*60)

thrift_files = [
    '/app/pkg/remote/codec/thrift/thrift.go',
    '/app/pkg/remote/codec/thrift/thrift_data.go'
]

for filepath in thrift_files:
    if os.path.exists(filepath):
        print(f"\nChecking {os.path.basename(filepath)}:")
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Check for the required functions
        if 'MarshalThriftData' in content:
            print("  ✓ MarshalThriftData found")
            # Check if it has Basic codec fallback logic
            if 'Basic' in content and ('FastCodec' in content or 'Frugal' in content):
                print("  ✓ Basic codec fallback logic present")
            else:
                print("  ⚠ Basic codec fallback logic unclear")
        else:
            print("  ✗ MarshalThriftData NOT found")
            
        if 'UnmarshalThriftData' in content:
            print("  ✓ UnmarshalThriftData found")
        else:
            print("  ✗ UnmarshalThriftData NOT found")

print("\n" + "="*60)
print("TARGET 6: Detailed gRPC Diagnostics Check")
print("="*60)

# Check frame_reader.go more carefully
frame_reader = '/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go'
if os.path.exists(frame_reader):
    with open(frame_reader, 'r') as f:
        lines = f.readlines()
    
    print(f"\nChecking {os.path.basename(frame_reader)}:")
    
    # Look for readAndCheckFrameHeader
    found_method = False
    found_hex = False
    for i, line in enumerate(lines):
        if 'readAndCheckFrameHeader' in line:
            print(f"  ✓ readAndCheckFrameHeader found at line {i+1}")
            print(f"    Line: {line.strip()}")
            found_method = True
            
            # Check surrounding lines for hex format
            context = ''.join(lines[max(0,i-5):min(len(lines),i+10)])
            if '%#x' in context:
                print(f"  ✓ Hex format (%#x) found in error handling")
                found_hex = True
    
    if not found_method:
        print("  ✗ readAndCheckFrameHeader NOT found")
    if found_method and not found_hex:
        print("  ⚠ readAndCheckFrameHeader found but hex format unclear")
else:
    print(f"  ✗ frame_reader.go FILE MISSING")

print("\n" + "="*60)
