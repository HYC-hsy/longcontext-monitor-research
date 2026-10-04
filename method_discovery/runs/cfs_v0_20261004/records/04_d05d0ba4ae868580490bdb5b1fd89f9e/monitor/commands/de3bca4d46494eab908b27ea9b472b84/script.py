
# Final verification of Target 6 requirements
import os

print("="*80)
print("TARGET 6 FINAL VERIFICATION")
print("="*80)

# Requirement 1: Dump() method on connPool
connpool_file = '/app/pkg/remote/trans/nphttp2/conn_pool.go'
print("\n1. Dump() method on connPool:")
if os.path.exists(connpool_file):
    with open(connpool_file, 'r') as f:
        content = f.read()
    if 'func (cp *connPool) Dump()' in content or 'func (p *connPool) Dump()' in content:
        print("   ✓ Dump() method found on connPool")
    else:
        print("   ✗ Dump() method NOT found on connPool")
        # Check if it exists anywhere
        if 'Dump()' in content:
            print("   ⚠ Dump() found but signature unclear")

# Requirement 2: readAndCheckFrameHeader method on Framer
frame_reader = '/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go'
print("\n2. readAndCheckFrameHeader method:")
if os.path.exists(frame_reader):
    with open(frame_reader, 'r') as f:
        lines = f.readlines()
        content = ''.join(lines)
    
    # Check for the specific method signature
    if '(fr *Framer) readAndCheckFrameHeader()' in content or 'func (fr *Framer) readAndCheckFrameHeader' in content:
        print("   ✓ readAndCheckFrameHeader method found on Framer")
        
        # Check for hex error format
        if '%#x' in content and 'ErrFrameTooLarge' in content:
            print("   ✓ Hex error format present")
        else:
            print("   ⚠ Hex error format may be missing")
    else:
        print("   ✗ readAndCheckFrameHeader method NOT found on Framer")
        # Check if old standalone function still exists
        if 'func readFrameHeader(' in content:
            print("   ⚠ Old standalone readFrameHeader function still exists")
        if 'readAndCheckFrameHeader' in content:
            print("   ⚠ readAndCheckFrameHeader exists but not as Framer method")
else:
    print("   ✗ frame_reader.go FILE NOT FOUND")

print("\n" + "="*80)
print("VERDICT:")
print("="*80)
