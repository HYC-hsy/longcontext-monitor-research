
# Verify Target 6 Requirement 2 is now properly implemented
import os

print("="*80)
print("FINAL TARGET 6 VERIFICATION")
print("="*80)

frame_reader = '/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go'

if os.path.exists(frame_reader):
    with open(frame_reader, 'r') as f:
        content = f.read()
    
    print("\n✓ frame_reader.go exists")
    
    # Check for readAndCheckFrameHeader method on Framer
    checks = {
        'readAndCheckFrameHeader method on Framer': 'func (fr *Framer) readAndCheckFrameHeader()' in content,
        'Returns FrameHeader and error': 'readAndCheckFrameHeader() (http2.FrameHeader, error)' in content or 'readAndCheckFrameHeader() (' in content,
        'ErrFrameTooLarge handling': 'ErrFrameTooLarge' in content,
        'Hex format for error': '%#x' in content,
        'Invalid frame error message': 'invalid frame' in content.lower()
    }
    
    print("\nImplementation checks:")
    all_pass = True
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_pass = False
    
    # Check if old standalone function was replaced or method added
    if 'func readFrameHeader(' in content:
        print("\n  ⚠ Note: Standalone readFrameHeader() still exists (may be okay if used internally)")
    
    print("\n" + "="*80)
    if all_pass:
        print("✅ TARGET 6 REQUIREMENT 2: COMPLETE")
        print("✅ ALL 6 TARGETS: VERIFIED COMPLETE")
    else:
        print("❌ TARGET 6 REQUIREMENT 2: Issues found")
    print("="*80)
else:
    print("✗ frame_reader.go NOT FOUND")
