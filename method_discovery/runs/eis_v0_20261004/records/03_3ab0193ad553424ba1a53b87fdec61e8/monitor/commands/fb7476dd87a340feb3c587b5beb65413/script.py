
# Verify TTHeaderFramed case is removed from transport/keys.go
with open('/app/transport/keys.go', 'r') as f:
    content = f.read()

if 'case TTHeaderFramed:' in content:
    print("❌ ERROR: TTHeaderFramed case still exists in switch")
    # Find and show it
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'TTHeaderFramed' in line:
            print(f"  Line {i+1}: {line}")
else:
    print("✓ TTHeaderFramed case successfully removed from String() switch")
    
# Also verify TTHeaderFramed constant is still defined
if 'TTHeaderFramed = TTHeader | Framed' in content:
    print("✓ TTHeaderFramed constant is still defined (as composite)")
else:
    print("❌ TTHeaderFramed constant definition not found")
