
# Verify the default protocol has been changed to Framed
with open('/app/pkg/rpcinfo/rpcconfig.go', 'r') as f:
    content = f.read()

print("=== Checking Default Protocol in rpcconfig.go ===\n")

# Find the initialize() function
if 'func (r *rpcConfig) initialize()' in content:
    start = content.find('func (r *rpcConfig) initialize()')
    end = content.find('\n}', start) + 2
    initialize_func = content[start:end]
    
    print("initialize() function:")
    print(initialize_func)
    
    # Check for transportProtocol assignment
    if 'transportProtocol = transport.Framed' in initialize_func:
        print("\n✓ Default is NOW Framed")
    elif 'transportProtocol = transport.PurePayload' in initialize_func or 'transportProtocol = 0' in initialize_func:
        print("\n❌ Default is still PurePayload")
    else:
        print("\n? Default protocol assignment not clear")
        
print("\n=== Checking SetTransportProtocol Logic ===\n")

# Find SetTransportProtocol function
if 'func (r *rpcConfig) SetTransportProtocol' in content:
    start = content.find('func (r *rpcConfig) SetTransportProtocol')
    end = content.find('\n}', start) + 2
    set_func = content[start:end]
    
    print("SetTransportProtocol() function:")
    print(set_func)
