
# More precise check for GRPCStreaming
with open('/app/transport/keys.go', 'r') as f:
    content = f.read()

print("=== Checking GRPCStreaming Constant ===\n")

# Show the actual constant definitions
import re
const_section = re.search(r'const \((.*?)\)', content, re.DOTALL)
if const_section:
    print("Constant definitions found:")
    print(const_section.group(1)[:500])
    
# Look specifically for GRPCStreaming
if 'GRPCStreaming' in content:
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'GRPCStreaming' in line:
            print(f"\nLine {i+1}: {line}")
            if '128' in line:
                print("✓ GRPCStreaming = 128 CONFIRMED")
            else:
                print("✗ GRPCStreaming does not equal 128")
else:
    print("✗ GRPCStreaming not found in file")
