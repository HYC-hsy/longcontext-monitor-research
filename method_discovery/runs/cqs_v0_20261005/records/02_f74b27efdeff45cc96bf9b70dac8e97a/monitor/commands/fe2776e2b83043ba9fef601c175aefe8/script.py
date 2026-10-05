
# Verify the default protocol in rpcconfig.go
with open('/app/pkg/rpcinfo/rpcconfig.go', 'r') as f:
    content = f.read()
    
print("=== Checking Default Protocol ===\n")

# Find the initialize() function
if 'func (r *rpcConfig) initialize()' in content:
    # Extract the initialize function
    start = content.find('func (r *rpcConfig) initialize()')
    end = content.find('\n}', start) + 2
    initialize_func = content[start:end]
    
    print("initialize() function:")
    print(initialize_func)
    
    # Check for transportProtocol assignment
    if 'transportProtocol = transport.Framed' in initialize_func:
        print("\n✓ Default is Framed")
    elif 'transportProtocol = transport.PurePayload' in initialize_func or 'transportProtocol = 0' in initialize_func:
        print("\n❌ Default is PurePayload (0)")
    else:
        print("\n? Default protocol assignment not found in initialize()")
else:
    print("initialize() function not found")

# Also check for any comment explaining the decision
import re
matches = re.findall(r'transportProtocol.*//.*', content)
if matches:
    print("\n=== Related Comments ===")
    for match in matches:
        print(match)
