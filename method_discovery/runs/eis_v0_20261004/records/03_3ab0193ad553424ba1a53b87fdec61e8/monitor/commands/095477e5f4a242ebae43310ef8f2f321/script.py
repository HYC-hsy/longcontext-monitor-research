
# Verify Target 6 implementation meets exact requirements
import re

with open('/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go', 'r') as f:
    content = f.read()
    lines = content.split('\n')

print("=== Target 6 Verification ===\n")

# Check 1: readAndCheckFrameHeader method exists
if 'func (fr *Framer) readAndCheckFrameHeader()' in content:
    print("✓ 1. readAndCheckFrameHeader method exists")
    for i, line in enumerate(lines):
        if 'func (fr *Framer) readAndCheckFrameHeader()' in line:
            print(f"   Found at line {i+1}: {line.strip()}")
            break
else:
    print("✗ 1. readAndCheckFrameHeader method NOT FOUND")

# Check 2: ReadFrame calls the new method
if 'fr.readAndCheckFrameHeader()' in content:
    print("\n✓ 2. ReadFrame() calls fr.readAndCheckFrameHeader()")
    for i, line in enumerate(lines):
        if 'fr.readAndCheckFrameHeader()' in line and 'ReadFrame' in ''.join(lines[max(0,i-20):i]):
            print(f"   Found at line {i+1}: {line.strip()}")
            break
else:
    print("\n✗ 2. ReadFrame() does NOT call fr.readAndCheckFrameHeader()")

# Check 3: Exact error format exists
error_pattern = r'first4Bytes=%#x.*second4Bytes=%#x'
if re.search(error_pattern, content):
    print("\n✓ 3. Exact error format with first4Bytes=%#x, second4Bytes=%#x found")
    for i, line in enumerate(lines):
        if 'first4Bytes=%#x' in line and 'second4Bytes=%#x' in line:
            print(f"   Found at line {i+1}")
            print(f"   {line.strip()}")
            break
else:
    print("\n✗ 3. Exact error format NOT FOUND")
    print("   Required: fmt.Errorf(...first4Bytes=%#x, second4Bytes=%#x...)")

# Check 4: Old readFrameHeader function still called?
old_calls = []
for i, line in enumerate(lines):
    if 'readFrameHeader(fr.reader)' in line or 'readFrameHeader(r)' in line:
        old_calls.append((i+1, line.strip()))

if old_calls:
    print(f"\n⚠️  4. Old readFrameHeader still called at {len(old_calls)} location(s):")
    for line_num, line in old_calls:
        print(f"   Line {line_num}: {line}")
else:
    print("\n✓ 4. Old readFrameHeader function not called in ReadFrame")

print("\n" + "="*60)
if all([
    'func (fr *Framer) readAndCheckFrameHeader()' in content,
    'fr.readAndCheckFrameHeader()' in content,
    re.search(error_pattern, content),
    len(old_calls) == 0 or all('ReadFrame' not in ''.join(lines[max(0,ln-20):ln]) for ln, _ in old_calls)
]):
    print("RESULT: ✅ Target 6 requirements VERIFIED")
else:
    print("RESULT: ❌ Target 6 requirements NOT MET")
