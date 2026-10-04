
import subprocess
import os

print("=== FINAL COMPREHENSIVE VERIFICATION OF ALL 6 TARGETS ===\n")

errors = []

# Target 1: Streaming Types
print("TARGET 1: Streaming Types")
checks = {
    'ClientStream': ['grep', '-q', 'type ClientStream interface', '/app/pkg/streaming/streaming.go'],
    'ServerStream': ['grep', '-q', 'type ServerStream interface', '/app/pkg/streaming/streaming.go'],
    'Header/Trailer': ['grep', '-q', 'type Header map\\[string\\]string', '/app/pkg/streaming/streaming.go'],
    'BidiStreamingClient': ['grep', '-q', 'type BidiStreamingClient\\[', '/app/pkg/streaming/streaming.go'],
    'EventHandler': ['grep', '-q', 'type EventHandler func', '/app/pkg/streaming/streaming.go'],
}
for name, cmd in checks.items():
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        errors.append(f"T1: {name} missing")
        print(f"  ✗ {name}")
    else:
        print(f"  ✓ {name}")

# Target 2: Endpoint Architecture
print("\nTARGET 2: Endpoint Architecture")
# Check cep/sep packages
for pkg in ['cep', 'sep']:
    if not os.path.exists(f'/app/pkg/endpoint/{pkg}/endpoint.go'):
        errors.append(f"T2: pkg/endpoint/{pkg} missing")
        print(f"  ✗ {pkg} package missing")
    else:
        print(f"  ✓ {pkg} package exists")

# Check UnaryEndpoint in BASE pkg/endpoint
result = subprocess.run(['grep', '-q', 'type UnaryEndpoint Endpoint', 
                        '/app/pkg/endpoint/endpoint.go'],
                       capture_output=True)
if result.returncode != 0:
    errors.append("T2: UnaryEndpoint not in base pkg/endpoint")
    print("  ✗ UnaryEndpoint in base package")
else:
    print("  ✓ UnaryEndpoint in base package")

# Check conversion methods
result = subprocess.run(['grep', '-q', 'ToMiddleware\\|ToUnaryMiddleware',
                        '/app/pkg/endpoint/endpoint.go'],
                       capture_output=True)
if result.returncode != 0:
    errors.append("T2: Conversion methods missing")
    print("  ✗ Conversion methods")
else:
    print("  ✓ Conversion methods")

# Check deprecated.go - this is OPTIONAL per agent's note that RecvEndpoint/SendEndpoint
# already exist as proper types, not deprecated aliases
if os.path.exists('/app/pkg/endpoint/deprecated.go'):
    print("  ✓ deprecated.go exists")
else:
    print("  ⚠ deprecated.go not created (agent says not needed)")

# Target 3: Transport Protocols
print("\nTARGET 3: Transport Protocols")
result = subprocess.run(['grep', '-E', 'TTHeaderStreaming.*=.*64', 
                        '/app/transport/keys.go'],
                       capture_output=True)
if result.returncode != 0:
    errors.append("T3: TTHeaderStreaming != 64")
    print("  ✗ TTHeaderStreaming = 64")
else:
    print("  ✓ TTHeaderStreaming = 64")

result = subprocess.run(['grep', '-E', 'GRPCStreaming.*=.*128',
                        '/app/transport/keys.go'],
                       capture_output=True)
if result.returncode != 0:
    errors.append("T3: GRPCStreaming != 128")
    print("  ✗ GRPCStreaming = 128")
else:
    print("  ✓ GRPCStreaming = 128")

# Target 4: Thrift Codec Fallback
print("\nTARGET 4: Thrift Codec Fallback")
with open('/app/pkg/remote/codec/thrift/thrift_data.go', 'r') as f:
    content = f.read()
    if 'if c.CodecType != Basic' in content:
        errors.append("T4: Bad condition 'if c.CodecType != Basic' still present")
        print("  ✗ Still has blocking condition")
    else:
        print("  ✓ Blocking condition removed")
    
    if 'if typecodec.FastCodec' not in content:
        errors.append("T4: FastCodec fallback missing")
        print("  ✗ FastCodec fallback")
    else:
        print("  ✓ FastCodec fallback present")

# Target 5: Client Options
print("\nTARGET 5: Client Options")
for f in ['option_unary.go', 'option_stream.go', 'option_ttstream.go']:
    if not os.path.exists(f'/app/client/{f}'):
        errors.append(f"T5: {f} missing")
        print(f"  ✗ {f}")
    else:
        print(f"  ✓ {f}")

# Check WithRecvTimeout
result = subprocess.run(['grep', '-rq', 'WithStreamRecvTimeout\\|WithRecvTimeout',
                        '/app/client/callopt/'],
                       capture_output=True)
if result.returncode != 0:
    errors.append("T5: WithRecvTimeout missing")
    print("  ✗ WithRecvTimeout")
else:
    print("  ✓ WithRecvTimeout")

# Check retry migration
result = subprocess.run(['grep', '-q', 'UnaryOptions.RetryMethodPolicies',
                        '/app/client/option.go'],
                       capture_output=True)
if result.returncode != 0:
    errors.append("T5: Retry migration incomplete")
    print("  ✗ Retry migration")
else:
    print("  ✓ Retry migration")

# Target 6: gRPC Diagnostics
print("\nTARGET 6: gRPC Diagnostics")
result = subprocess.run(['grep', '-q', 'func.*Dump.*interface',
                        '/app/pkg/remote/trans/nphttp2/conn_pool.go'],
                       capture_output=True)
if result.returncode != 0:
    errors.append("T6: Dump() method missing")
    print("  ✗ Dump() method")
else:
    print("  ✓ Dump() method")

result = subprocess.run(['grep', '-q', 'readAndCheckFrameHeader',
                        '/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go'],
                       capture_output=True)
if result.returncode != 0:
    errors.append("T6: readAndCheckFrameHeader missing")
    print("  ✗ readAndCheckFrameHeader")
else:
    print("  ✓ readAndCheckFrameHeader")

# Final compilation check
print("\n" + "="*60)
print("COMPILATION CHECK")
print("="*60)
result = subprocess.run(['go', 'build', './...'], cwd='/app',
                       capture_output=True, text=True, timeout=60)
if result.returncode != 0:
    errors.append("COMPILATION FAILED")
    print(f"✗ COMPILATION FAILED:\n{result.stderr[:500]}")
else:
    print("✓ Full project compiles successfully")

print("\n" + "="*60)
if errors:
    print(f"❌ VERIFICATION FAILED - {len(errors)} issues:")
    for err in errors:
        print(f"  • {err}")
    print("\nCANNOT APPROVE COMPLETION")
else:
    print("✅ ALL 6 TARGETS VERIFIED - READY FOR COMPLETION")
print("="*60)
