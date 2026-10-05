
# More careful verification of the two failed checks
import re

print("=== Investigating Potential False Negatives ===\n")

# Check 1: sep StreamEndpoint signature
print("1. Checking sep/endpoint.go for StreamEndpoint signature:")
with open('/app/pkg/endpoint/sep/endpoint.go', 'r') as f:
    sep_content = f.read()
    
# Look for StreamEndpoint definition
sep_match = re.search(r'type StreamEndpoint\s+func\([^)]+\)', sep_content)
if sep_match:
    print(f"   Found: {sep_match.group()}")
    # Check if it takes ServerStream parameter
    if 'streaming.ServerStream' in sep_match.group():
        print("   ✓ Correct: Takes ServerStream parameter")
    else:
        print("   ✗ Issue: Does not take ServerStream parameter")
else:
    print("   ✗ StreamEndpoint not found")

# Check 2: GRPCStreaming constant
print("\n2. Checking transport/keys.go for GRPCStreaming:")
with open('/app/transport/keys.go', 'r') as f:
    transport_content = f.read()
    
# Look for GRPCStreaming
grpc_match = re.search(r'GRPCStreaming\s+Protocol\s*=\s*\d+', transport_content)
if grpc_match:
    print(f"   Found: {grpc_match.group()}")
    if '128' in grpc_match.group():
        print("   ✓ Correct: Value is 128")
    else:
        print(f"   ✗ Issue: Value is not 128")
else:
    print("   ✗ GRPCStreaming not found")

print("\n=== Detailed Check ===")
# Show the actual lines
print("\nsep StreamEndpoint (first 200 chars):")
start = sep_content.find('type StreamEndpoint')
if start != -1:
    print(sep_content[start:start+200])
else:
    print("Not found")

print("\nGRPCStreaming constant (context):")
start = transport_content.find('GRPCStreaming')
if start != -1:
    print(transport_content[max(0,start-50):start+100])
else:
    print("Not found")
