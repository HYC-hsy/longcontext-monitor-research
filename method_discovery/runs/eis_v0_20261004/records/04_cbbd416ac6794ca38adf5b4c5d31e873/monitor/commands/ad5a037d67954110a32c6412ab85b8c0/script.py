
# Verify the 6 original targets are actually implemented
import subprocess
import json

results = {}

# Target 1: Check streaming types exist
print("=== TARGET 1: Streaming Types ===")
result = subprocess.run(
    ['grep', '-l', 'ClientStream\|ServerStream\|BidiStreamingClient', 
     '/app/pkg/streaming/streaming.go'],
    capture_output=True, text=True
)
results['target1_streaming_types'] = result.returncode == 0
print(f"Streaming types found: {results['target1_streaming_types']}")

# Target 2: Check endpoint packages exist
print("\n=== TARGET 2: Endpoint Packages ===")
import os
results['target2_cep'] = os.path.exists('/app/pkg/endpoint/cep')
results['target2_sep'] = os.path.exists('/app/pkg/endpoint/sep')
print(f"pkg/endpoint/cep exists: {results['target2_cep']}")
print(f"pkg/endpoint/sep exists: {results['target2_sep']}")

# Target 3: Check transport protocol constants
print("\n=== TARGET 3: Transport Protocols ===")
result = subprocess.run(
    ['grep', '-E', 'TTHeaderStreaming.*=.*64|GRPCStreaming.*=.*128',
     '/app/transport/keys.go'],
    capture_output=True, text=True
)
results['target3_protocols'] = result.returncode == 0
print(f"Protocol constants correct: {results['target3_protocols']}")
if results['target3_protocols']:
    print(result.stdout[:200])

# Target 4: Check thrift codec
print("\n=== TARGET 4: Thrift Codec Fallback ===")
result = subprocess.run(
    ['grep', '-l', 'MarshalThriftData\|UnmarshalThriftData',
     '/app/pkg/remote/codec/thrift/thrift.go'],
    capture_output=True, text=True
)
results['target4_thrift'] = result.returncode == 0
print(f"Thrift codec file exists: {results['target4_thrift']}")

# Target 5: Check client options
print("\n=== TARGET 5: Client Options ===")
opt_files = [
    '/app/client/option_unary.go',
    '/app/client/option_stream.go', 
    '/app/client/option_ttstream.go'
]
for f in opt_files:
    exists = os.path.exists(f)
    results[f'target5_{os.path.basename(f)}'] = exists
    print(f"{os.path.basename(f)} exists: {exists}")

# Check WithRecvTimeout in streamcall
result = subprocess.run(
    ['grep', '-r', 'WithRecvTimeout\|WithStreamRecvTimeout',
     '/app/client/callopt/'],
    capture_output=True, text=True
)
results['target5_recv_timeout'] = result.returncode == 0
print(f"WithRecvTimeout found: {results['target5_recv_timeout']}")

# Target 6: Check gRPC diagnostics  
print("\n=== TARGET 6: gRPC Diagnostics ===")
result = subprocess.run(
    ['grep', '-l', 'func.*Dump',
     '/app/pkg/remote/trans/nphttp2/conn_pool.go'],
    capture_output=True, text=True
)
results['target6_dump'] = result.returncode == 0
print(f"Dump() method exists: {results['target6_dump']}")

result = subprocess.run(
    ['grep', '-l', 'readAndCheckFrameHeader',
     '/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go'],
    capture_output=True, text=True
)
results['target6_frame'] = result.returncode == 0
print(f"readAndCheckFrameHeader exists: {results['target6_frame']}")

print("\n=== SUMMARY ===")
all_good = all(results.values())
print(f"All targets implemented: {all_good}")
print(json.dumps(results, indent=2))
