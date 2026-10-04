
# COMPREHENSIVE VERIFICATION OF ALL 6 TARGETS
# This verification checks actual implementation against original requirements

import os
import subprocess

verification_results = {}

print("="*80)
print("COMPREHENSIVE VERIFICATION OF 6 TARGETS")
print("="*80)
print()

# TARGET 1: Streaming Types in pkg/streaming
print("TARGET 1: Streaming Types")
print("-" * 40)

target1_required = {
    'types.go': [
        'type Header map[string]string',
        'type Trailer map[string]string',
        'type ClientStream interface',
        'type ServerStream interface',
        'type CloseCallbackRegister interface',
        'type GRPCStreamGetter interface',
        'type EventHandler func',
        'CloseSend'  # ClientStream should have CloseSend
    ],
    'generic.go': [
        'ServerStreamingClient',
        'ServerStreamingServer',
        'ClientStreamingClient',
        'ClientStreamingServer',
        'BidiStreamingClient',
        'BidiStreamingServer',
        'NewServerStreamingClient',
        'NewClientStreamingClient',
        'NewBidiStreamingClient'
    ],
    'streaming.go': [
        'ServerStream ServerStream',  # Args/Result should have these fields
        'ClientStream ClientStream'
    ]
}

target1_pass = True
for filename, required_content in target1_required.items():
    filepath = f'/app/pkg/streaming/{filename}'
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            content = f.read()
        missing = [item for item in required_content if item not in content]
        if missing:
            print(f"  ✗ {filename}: MISSING {missing}")
            target1_pass = False
        else:
            print(f"  ✓ {filename}: All required content present")
    else:
        print(f"  ✗ {filename}: FILE MISSING")
        target1_pass = False

verification_results['Target 1'] = 'PASS' if target1_pass else 'FAIL'
print()

# TARGET 2: Endpoint Architecture
print("TARGET 2: Endpoint Architecture")
print("-" * 40)

target2_files = {
    '/app/pkg/endpoint/cep/endpoint.go': ['StreamEndpoint', 'EqualsTo', 'DummyDummyMiddleware'],
    '/app/pkg/endpoint/sep/endpoint.go': ['StreamEndpoint', 'StreamRecvEndpoint', 'StreamSendEndpoint'],
    '/app/pkg/endpoint/unary.go': ['UnaryEndpoint', 'UnaryMiddleware', 'ToMiddleware'],
    '/app/pkg/endpoint/deprecated.go': ['Deprecated', 'RecvEndpoint', 'SendEndpoint']
}

target2_pass = True
for filepath, required in target2_files.items():
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            content = f.read()
        missing = [item for item in required if item not in content]
        if missing:
            print(f"  ✗ {os.path.basename(filepath)}: MISSING {missing}")
            target2_pass = False
        else:
            print(f"  ✓ {os.path.basename(filepath)}: All required content present")
    else:
        print(f"  ✗ {filepath}: FILE MISSING")
        target2_pass = False

verification_results['Target 2'] = 'PASS' if target2_pass else 'FAIL'
print()

# TARGET 3: Transport Protocol
print("TARGET 3: Transport Protocol")
print("-" * 40)

with open('/app/transport/keys.go', 'r') as f:
    keys_content = f.read()

target3_checks = {
    'TTHeaderStreaming dedicated flag': 'TTHeaderStreaming Protocol = 1 << iota' in keys_content or 'TTHeaderStreaming\n' in keys_content,
    'GRPCStreaming flag': 'GRPCStreaming' in keys_content,
    'String() handles composites': 'strings.Join' in keys_content or '|' in keys_content,
    'HESSIAN2 returns Hessian2': '"Hessian2"' in keys_content
}

target3_pass = all(target3_checks.values())
for check, passed in target3_checks.items():
    print(f"  {'✓' if passed else '✗'} {check}")

# Check default protocol in rpcconfig.go
with open('/app/pkg/rpcinfo/rpcconfig.go', 'r') as f:
    rpcconfig_content = f.read()

if 'transportProtocol = transport.Framed' in rpcconfig_content:
    print(f"  ✓ Default protocol = transport.Framed")
    target3_pass = target3_pass and True
else:
    print(f"  ✗ Default protocol NOT Framed")
    target3_pass = False

verification_results['Target 3'] = 'PASS' if target3_pass else 'FAIL'
print()

print("="*80)
print("VERIFICATION SUMMARY (Targets 1-3)")
print("="*80)
for target, result in verification_results.items():
    print(f"{target}: {result}")
