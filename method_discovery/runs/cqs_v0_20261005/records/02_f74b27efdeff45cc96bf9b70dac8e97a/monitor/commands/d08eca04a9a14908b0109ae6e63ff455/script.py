
# Quick verification that default is still Framed
with open('/app/pkg/rpcinfo/rpcconfig.go', 'r') as f:
    content = f.read()
    
print("=== Verification of Target 3 Requirement 3 ===\n")

# Check default protocol
if 'transportProtocol = transport.Framed' in content and 'func (r *rpcConfig) initialize()' in content:
    print("✓ Default protocol is Framed")
else:
    print("❌ Default protocol issue detected")

# Quick summary of all targets
print("\n=== All Targets Status ===")
import os

targets = [
    ("Target 1: Streaming types", "/app/pkg/streaming/streaming.go", ["ClientStream", "ServerStream", "BidiStreamingClient"]),
    ("Target 2: Endpoint packages", "/app/pkg/endpoint/cep/endpoint.go", ["StreamEndpoint", "StreamRecvEndpoint", "EqualsTo", "DummyDummyMiddleware"]),
    ("Target 2: UnaryEndpoint", "/app/pkg/endpoint/endpoint.go", ["UnaryMiddlewareBuilder", "UnaryChain", "ToMiddleware"]),
    ("Target 3: Protocol String()", "/app/transport/keys.go", ["TTHeaderStreaming", "GRPCStreaming", "pipe-separated"]),
    ("Target 5: Client options", "/app/client/option.go", ["UnaryOption", "StreamOption", "TTHeaderStreamingOption"]),
]

for target_name, file_path, keywords in targets:
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            file_content = f.read()
        found = sum(1 for kw in keywords if kw in file_content)
        status = "✓" if found >= len(keywords) - 1 else "?"
        print(f"{status} {target_name}: {found}/{len(keywords)} keywords present")
    else:
        print(f"❌ {target_name}: file not found")
