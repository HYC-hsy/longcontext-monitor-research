
import sys
sys.path.insert(0, '/app')

# Test the String() method for transport protocol
with open('/app/transport/keys.go', 'r') as f:
    content = f.read()
    
# Check if TTHeaderFramed case exists in the switch
if 'case TTHeaderFramed:' in content:
    # Find what it returns
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'case TTHeaderFramed:' in line:
            # Next line should be the return
            print(f"Line {i}: {line}")
            if i+1 < len(lines):
                print(f"Line {i+1}: {lines[i+1]}")
            break
    print("\n❌ ISSUE: TTHeaderFramed has a dedicated case that returns 'TTHeaderFramed'")
    print("Required: TTHeaderFramed.String() → \"TTHeader|Framed\"")
else:
    print("✓ TTHeaderFramed has no dedicated case, will use composite handling")
