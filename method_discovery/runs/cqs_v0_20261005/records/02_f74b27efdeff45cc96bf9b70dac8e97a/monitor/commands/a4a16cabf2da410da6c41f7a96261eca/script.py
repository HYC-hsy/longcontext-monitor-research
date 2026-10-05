
# Verify the sep.StreamEndpoint signature has been corrected
with open('/app/pkg/endpoint/sep/endpoint.go', 'r') as f:
    sep_content = f.read()

print("=== Verification of sep.StreamEndpoint Fix ===\n")

# Find the StreamEndpoint definition
import re
sep_match = re.search(r'type StreamEndpoint\s+func\([^)]+\)[^{]*', sep_content)
if sep_match:
    print("Found StreamEndpoint definition:")
    print(f"  {sep_match.group()}")
    
    # Check the signature
    signature = sep_match.group()
    takes_serverstream = 'st streaming.ServerStream' in signature and ') (err error)' in signature
    returns_serverstream = ') (st streaming.ServerStream' in signature
    
    if takes_serverstream and not returns_serverstream:
        print("\n✓ CORRECT: Takes ServerStream parameter, returns only error")
    elif returns_serverstream:
        print("\n✗ STILL WRONG: Returns ServerStream instead of taking it as parameter")
    else:
        print(f"\n? UNCLEAR: Signature doesn't match expected pattern")
else:
    print("✗ StreamEndpoint definition not found")

# For comparison, verify cep.StreamEndpoint is still correct
print("\n=== Verification of cep.StreamEndpoint (should return ClientStream) ===\n")
with open('/app/pkg/endpoint/cep/endpoint.go', 'r') as f:
    cep_content = f.read()

cep_match = re.search(r'type StreamEndpoint\s+func\([^)]+\)[^{]*', cep_content)
if cep_match:
    print("Found StreamEndpoint definition:")
    print(f"  {cep_match.group()}")
    
    signature = cep_match.group()
    returns_clientstream = 'streaming.ClientStream' in signature and ') (st streaming.ClientStream' in signature
    
    if returns_clientstream:
        print("\n✓ CORRECT: Returns ClientStream as expected")
    else:
        print("\n✗ WRONG: Should return ClientStream")
