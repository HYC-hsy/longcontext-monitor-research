
# Final comprehensive verification of all 6 targets
import subprocess
import json

print("=== FINAL VERIFICATION OF ALL 6 TARGETS ===\n")

results = {}

# Target 1: Streaming Types - verify key types exist
print("TARGET 1: Streaming Types")
checks = [
    ('ClientStream', '/app/pkg/streaming/streaming.go'),
    ('ServerStream', '/app/pkg/streaming/streaming.go'),
    ('BidiStreamingClient', '/app/pkg/streaming/streaming.go'),
    ('Header.*map\\[string\\]string', '/app/pkg/streaming/streaming.go'),
    ('EventHandler', '/app/pkg/streaming/streaming.go')
]
for check, path in checks:
    result = subprocess.run(['grep', '-E', check, path], 
                          capture_output=True, text=True)
    results[f't1_{check.split("[")[0]}'] = result.returncode == 0
print(f"✓ All streaming types present: {all(v for k,v in results.items() if k.startswith('t1_'))}")

# Target 2: Endpoint packages
print("\nTARGET 2: Endpoint Packages")
import os
results['t2_cep'] = os.path.exists('/app/pkg/endpoint/cep/endpoint.go')
results['t2_sep'] = os.path.exists('/app/pkg/endpoint/sep/endpoint.go')
results['t2_unary'] = subprocess.run(['grep', 'type UnaryEndpoint', 
                                     '/app/pkg/endpoint/endpoint.go'],
                                    capture_output=True, text=True).returncode == 0
print(f"✓ cep package: {results['t2_cep']}")
print(f"✓ sep package: {results['t2_sep']}")
print(f"✓ UnaryEndpoint: {results['t2_unary']}")

# Target 3: Transport protocols
print("\nTARGET 3: Transport Protocols")
result = subprocess.run(['grep', '-E', 'TTHeaderStreaming.*=.*64|GRPCStreaming.*=.*128',
                        '/app/transport/keys.go'],
                       capture_output=True, text=True)
results['t3_constants'] = result.returncode == 0
result = subprocess.run(['grep', 'func.*String.*string', '/app/transport/keys.go'],
                       capture_output=True, text=True)
results['t3_string'] = result.returncode == 0
print(f"✓ Protocol constants correct: {results['t3_constants']}")
print(f"✓ String() method present: {results['t3_string']}")

# Target 4: Thrift codec fallback - verify fix
print("\nTARGET 4: Thrift Codec Fallback")
with open('/app/pkg/remote/codec/thrift/thrift_data.go', 'r') as f:
    content = f.read()
    # Check that fallback is NOT wrapped in "if c.CodecType != Basic"
    has_bad_condition = 'if c.CodecType != Basic' in content
    has_fastcodec_fallback = 'if typecodec.FastCodec {' in content and 'fastMarshalData' in content
    has_frugal_fallback = 'if typecodec.Frugal {' in content and 'frugalMarshalData' in content
    
results['t4_no_bad_condition'] = not has_bad_condition
results['t4_fastcodec'] = has_fastcodec_fallback
results['t4_frugal'] = has_frugal_fallback
print(f"✓ No 'if CodecType != Basic' blocking fallback: {results['t4_no_bad_condition']}")
print(f"✓ FastCodec fallback present: {results['t4_fastcodec']}")
print(f"✓ Frugal fallback present: {results['t4_frugal']}")

# Target 5: Client options
print("\nTARGET 5: Client Options")
opt_files = ['option_unary.go', 'option_stream.go', 'option_ttstream.go']
for f in opt_files:
    results[f't5_{f}'] = os.path.exists(f'/app/client/{f}')
    print(f"✓ {f}: {results[f't5_{f}']}")

result = subprocess.run(['grep', '-r', 'WithStreamRecvTimeout\\|WithRecvTimeout',
                        '/app/client/callopt/'],
                       capture_output=True, text=True)
results['t5_recv_timeout'] = result.returncode == 0
print(f"✓ WithRecvTimeout: {results['t5_recv_timeout']}")

result = subprocess.run(['grep', 'UnaryOptions.RetryMethodPolicies',
                        '/app/client/option.go'],
                       capture_output=True, text=True)
results['t5_retry_migration'] = result.returncode == 0
print(f"✓ Retry migration to UnaryOptions: {results['t5_retry_migration']}")

# Target 6: gRPC diagnostics
print("\nTARGET 6: gRPC Diagnostics")
result = subprocess.run(['grep', 'func.*Dump', 
                        '/app/pkg/remote/trans/nphttp2/conn_pool.go'],
                       capture_output=True, text=True)
results['t6_dump'] = result.returncode == 0
result = subprocess.run(['grep', 'readAndCheckFrameHeader',
                        '/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go'],
                       capture_output=True, text=True)
results['t6_frame'] = result.returncode == 0
print(f"✓ Dump() method: {results['t6_dump']}")
print(f"✓ readAndCheckFrameHeader: {results['t6_frame']}")

# Final summary
print("\n" + "="*50)
all_pass = all(results.values())
print(f"ALL TARGETS COMPLETE: {all_pass}")
print("="*50)

if not all_pass:
    print("\nFailed checks:")
    for k, v in results.items():
        if not v:
            print(f"  ✗ {k}")
