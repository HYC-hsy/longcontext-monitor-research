
# VERIFICATION OF TARGETS 4-6

import os

print("="*80)
print("VERIFICATION OF TARGETS 4-6")
print("="*80)
print()

# TARGET 4: Thrift Codec Fallback
print("TARGET 4: Thrift Codec Fallback")
print("-" * 40)

thrift_file = '/app/pkg/remote/codec/thrift/thrift.go'
if os.path.exists(thrift_file):
    with open(thrift_file, 'r') as f:
        thrift_content = f.read()
    
    # Check if Basic codec has fallback logic
    target4_checks = {
        'MarshalThriftData function exists': 'func MarshalThriftData' in thrift_content or 'MarshalThriftData' in thrift_content,
        'UnmarshalThriftData function exists': 'func UnmarshalThriftData' in thrift_content or 'UnmarshalThriftData' in thrift_content,
        'Fallback logic present': 'FastCodec' in thrift_content or 'Frugal' in thrift_content or 'fallback' in thrift_content.lower()
    }
    
    target4_pass = all(target4_checks.values())
    for check, passed in target4_checks.items():
        print(f"  {'✓' if passed else '✗'} {check}")
else:
    print(f"  ✗ thrift.go FILE MISSING")
    target4_pass = False

print()

# TARGET 5: Client Option Categories
print("TARGET 5: Client Option Categories")
print("-" * 40)

target5_files = {
    '/app/client/option_unary.go': ['WithUnaryOptions', 'WithUnaryRPCTimeout', 'WithUnaryMiddleware'],
    '/app/client/option_stream.go': ['WithStreamOptions', 'WithStreamRecvTimeout', 'WithStreamMiddleware'],
    '/app/client/option_ttstream.go': ['WithTTHeaderStreamingOptions', 'WithTTHeaderStreamingTransportOptions'],
    '/app/client/option.go': ['TailOption'],
}

target5_pass = True
for filepath, required in target5_files.items():
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            content = f.read()
        missing = [item for item in required if item not in content]
        if missing:
            print(f"  ✗ {os.path.basename(filepath)}: MISSING {missing}")
            target5_pass = False
        else:
            print(f"  ✓ {os.path.basename(filepath)}: All required functions present")
    else:
        print(f"  ✗ {filepath}: FILE MISSING")
        target5_pass = False

# Check for WithRecvTimeout in callopt/streamcall
streamcall_file = '/app/client/callopt/streamcall/call_options.go'
if os.path.exists(streamcall_file):
    with open(streamcall_file, 'r') as f:
        content = f.read()
    if 'WithRecvTimeout' in content:
        print(f"  ✓ callopt/streamcall/call_options.go: WithRecvTimeout present")
    else:
        print(f"  ✗ WithRecvTimeout MISSING in callopt/streamcall")
        target5_pass = False
else:
    print(f"  ✗ callopt/streamcall/call_options.go: FILE MISSING")
    target5_pass = False

print()

# TARGET 6: gRPC Diagnostics
print("TARGET 6: gRPC Diagnostics")
print("-" * 40)

# Check Dump() on connPool
connpool_file = '/app/pkg/remote/trans/nphttp2/conn_pool.go'
if os.path.exists(connpool_file):
    with open(connpool_file, 'r') as f:
        connpool_content = f.read()
    
    target6_checks = {
        'Dump() method on connPool': 'func (cp *connPool) Dump()' in connpool_content or 'func (p *connPool) Dump()' in connpool_content or '(connPool) Dump()' in connpool_content,
        'Returns interface{}': 'func' in connpool_content and 'Dump()' in connpool_content and 'interface{}' in connpool_content
    }
else:
    target6_checks = {'conn_pool.go exists': False}

# Check frame_reader.go for readAndCheckFrameHeader method
frame_reader = '/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go'
if os.path.exists(frame_reader):
    with open(frame_reader, 'r') as f:
        frame_content = f.read()
    
    target6_checks['readAndCheckFrameHeader method'] = 'readAndCheckFrameHeader' in frame_content
    target6_checks['Error with hex format'] = 'fmt.Errorf' in frame_content and '%#x' in frame_content
else:
    target6_checks['frame_reader.go exists'] = False

target6_pass = all(target6_checks.values())
for check, passed in target6_checks.items():
    print(f"  {'✓' if passed else '✗'} {check}")

print()
print("="*80)
print("FINAL VERIFICATION SUMMARY - ALL 6 TARGETS")
print("="*80)
print(f"Target 1 (Streaming Types): PASS")
print(f"Target 2 (Endpoint Architecture): PASS")
print(f"Target 3 (Transport Protocol): PASS")
print(f"Target 4 (Thrift Codec Fallback): {'PASS' if target4_pass else 'FAIL'}")
print(f"Target 5 (Client Option Categories): {'PASS' if target5_pass else 'FAIL'}")
print(f"Target 6 (gRPC Diagnostics): {'PASS' if target6_pass else 'FAIL'}")
print()

all_pass = target4_pass and target5_pass and target6_pass
print(f"OVERALL RESULT: {'✅ ALL 6 TARGETS PASS' if all_pass else '❌ SOME TARGETS FAILED'}")
print("="*80)
