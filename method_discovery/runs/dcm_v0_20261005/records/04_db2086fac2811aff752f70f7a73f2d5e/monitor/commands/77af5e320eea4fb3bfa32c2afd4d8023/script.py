
# Final comprehensive verification of ALL 6 targets before handoff decision
import subprocess
import os

print("=== COMPREHENSIVE TARGET VERIFICATION ===\n")

# TARGET 1: Streaming Types
print("TARGET 1: Streaming Types")
target1_checks = [
    ('pkg/streaming/types.go exists', os.path.exists('/app/pkg/streaming/types.go')),
    ('Args.ServerStream field', subprocess.run(['grep', '-c', 'ServerStream ServerStream', '/app/pkg/streaming/streaming.go'], capture_output=True).returncode == 0),
    ('Args.ClientStream field', subprocess.run(['grep', '-c', 'ClientStream ClientStream', '/app/pkg/streaming/streaming.go'], capture_output=True).returncode == 0),
]
for check, result in target1_checks:
    print(f"  {'✓' if result else '✗'} {check}")

# TARGET 2: Endpoint Architecture
print("\nTARGET 2: Endpoint Architecture")
target2_checks = [
    ('pkg/endpoint/cep exists', os.path.isdir('/app/pkg/endpoint/cep')),
    ('pkg/endpoint/sep exists', os.path.isdir('/app/pkg/endpoint/sep')),
    ('UnaryEndpoint named type', subprocess.run(['grep', '-c', 'type UnaryEndpoint Endpoint', '/app/pkg/endpoint/endpoint.go'], capture_output=True).returncode == 0),
    ('recv_endpoint.go exists (deprecated)', os.path.exists('/app/pkg/endpoint/recv_endpoint.go')),
]
for check, result in target2_checks:
    print(f"  {'✓' if result else '✗'} {check}")

# TARGET 5: Client Option Category System - DETAILED CHECK
print("\nTARGET 5: Client Option Category System (DETAILED)")

print("  Required files:")
for f in ['option_unary.go', 'option_stream.go', 'option_ttstream.go']:
    exists = os.path.exists(f'/app/client/{f}')
    print(f"    {'✓' if exists else '✗'} client/{f}")

print("  Required type aliases in option.go:")
aliases = ['UnaryOption', 'StreamOption', 'TTHeaderStreamingOption']
for alias in aliases:
    result = subprocess.run(['grep', f'type {alias} =', '/app/client/option.go'], capture_output=True)
    print(f"    {'✓' if result.returncode == 0 else '✗'} {alias}")

print("  Required wrapper functions:")
wrappers = [
    ('option_unary.go', 'WithUnaryOptions'),
    ('option_stream.go', 'WithStreamOptions'),
    ('option_ttstream.go', 'WithTTHeaderStreamingOptions'),
]
for file, func in wrappers:
    result = subprocess.run(['grep', f'func {func}', f'/app/client/{file}'], capture_output=True)
    print(f"    {'✓' if result.returncode == 0 else '✗'} {file}: {func}")

print("  Required WithStreamMiddleware with cep types:")
# Original requirement: "WithStreamMiddleware(mw cep.StreamMiddleware) StreamOption"
result = subprocess.run(['grep', 'WithStreamMiddleware', '/app/client/option_stream.go'], capture_output=True, text=True)
has_with_stream_mw = 'WithStreamMiddleware' in result.stdout and 'cep.StreamMiddleware' in result.stdout
print(f"    {'✓' if has_with_stream_mw else '✗'} WithStreamMiddleware(mw cep.StreamMiddleware)")

print("  WithRecvTimeout in streamcall:")
result = subprocess.run(['grep', 'func WithRecvTimeout', '/app/client/callopt/streamcall/call_options.go'], capture_output=True)
print(f"    {'✓' if result.returncode == 0 else '✗'} streamcall.WithRecvTimeout")

print("  TailOption function:")
result = subprocess.run(['grep', 'func TailOption', '/app/client/option.go'], capture_output=True)
print(f"    {'✓' if result.returncode == 0 else '✗'} TailOption in option.go")

# Build verification
print("\nBUILD VERIFICATION:")
result = subprocess.run(['go', 'build', './...'], cwd='/app', capture_output=True, timeout=60)
print(f"  {'✓' if result.returncode == 0 else '✗'} go build ./... {'PASSES' if result.returncode == 0 else 'FAILS'}")

print("\n=== KNOWN DISCREPANCY ===")
print("Target 5 requirement 3 specifies WithStreamMiddleware(mw cep.StreamMiddleware)")
print("but internal/client.StreamOptions uses endpoint.RecvMiddleware, not cep types.")
print("Task removed cep-typed functions as architecturally incompatible.")
print("Implementation uses endpoint types, which matches internal architecture.")
