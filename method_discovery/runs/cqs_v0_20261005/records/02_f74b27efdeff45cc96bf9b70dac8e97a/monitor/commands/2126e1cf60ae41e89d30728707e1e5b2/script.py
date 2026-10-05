
# Targeted verification that distinguishes complete vs incomplete states
# Focus on the most critical and specific requirements

print("=" * 70)
print("TARGETED ROOT VERIFICATION - DISTINGUISHING CHECKS")
print("=" * 70)

import re

critical_issues = []

# CRITICAL CHECK 1: sep.StreamEndpoint signature (was wrong in my intervention)
print("\n1. sep.StreamEndpoint signature (Target 2, req 2):")
with open('/app/pkg/endpoint/sep/endpoint.go', 'r') as f:
    sep_content = f.read()
sep_match = re.search(r'type StreamEndpoint\s+func\([^)]+\)[^{]*', sep_content)
if sep_match:
    sig = sep_match.group()
    print(f"   Found: {sig[:100]}")
    correct = 'st streaming.ServerStream) (err error)' in sig
    print(f"   {'✓ CORRECT' if correct else '✗ WRONG'}: Takes ServerStream param, returns error")
    if not correct:
        critical_issues.append("sep.StreamEndpoint has wrong signature")
else:
    print("   ✗ StreamEndpoint not found")
    critical_issues.append("sep.StreamEndpoint missing")

# CRITICAL CHECK 2: Default protocol is Framed (was PurePayload, I rejected completion for this)
print("\n2. Default transport protocol (Target 3, req 3):")
with open('/app/pkg/rpcinfo/rpcconfig.go', 'r') as f:
    rpc_content = f.read()
init_match = re.search(r'func \(r \*rpcConfig\) initialize\(\) \{[^}]+\}', rpc_content, re.DOTALL)
if init_match:
    init_func = init_match.group()
    if 'transportProtocol = transport.Framed' in init_func:
        print("   ✓ CORRECT: Default is transport.Framed")
    elif 'transportProtocol = transport.PurePayload' in init_func or 'transportProtocol = 0' in init_func:
        print("   ✗ WRONG: Default is PurePayload")
        critical_issues.append("Default protocol is PurePayload, not Framed")
    else:
        print("   ? UNCLEAR: Cannot determine default")
        critical_issues.append("Cannot verify default protocol")
else:
    print("   ✗ initialize() not found")
    critical_issues.append("initialize() function missing")

# CRITICAL CHECK 3: EqualsTo methods exist (was missing in my intervention)
print("\n3. EqualsTo methods on StreamRecvEndpoint/StreamSendEndpoint (Target 2, req 1):")
with open('/app/pkg/endpoint/cep/endpoint.go', 'r') as f:
    cep_content = f.read()
recv_equals = 'func (e StreamRecvEndpoint) EqualsTo' in cep_content
send_equals = 'func (e StreamSendEndpoint) EqualsTo' in cep_content
print(f"   {'✓' if recv_equals else '✗'} StreamRecvEndpoint.EqualsTo: {recv_equals}")
print(f"   {'✓' if send_equals else '✗'} StreamSendEndpoint.EqualsTo: {send_equals}")
if not (recv_equals and send_equals):
    critical_issues.append("EqualsTo methods missing")

# CRITICAL CHECK 4: UnaryMiddlewareBuilder, UnaryChain, conversion methods (was missing in my intervention)
print("\n4. UnaryEndpoint components (Target 2, req 3):")
with open('/app/pkg/endpoint/endpoint.go', 'r') as f:
    ep_content = f.read()
checks = {
    'UnaryMiddlewareBuilder': 'type UnaryMiddlewareBuilder' in ep_content,
    'UnaryChain': 'func UnaryChain' in ep_content,
    'ToMiddleware': 'func (mw UnaryMiddleware) ToMiddleware' in ep_content,
    'ToUnaryMiddleware': 'func (mw Middleware) ToUnaryMiddleware' in ep_content
}
for name, present in checks.items():
    print(f"   {'✓' if present else '✗'} {name}: {present}")
if not all(checks.values()):
    critical_issues.append("UnaryEndpoint components incomplete")

# CRITICAL CHECK 5: DummyDummyMiddleware (double Dummy is intentional, was missing)
print("\n5. DummyDummyMiddleware (note double 'Dummy'):")
dummy_cep = 'func DummyDummyMiddleware' in cep_content
with open('/app/pkg/endpoint/sep/endpoint.go', 'r') as f:
    sep_content = f.read()
dummy_sep = 'func DummyDummyMiddleware' in sep_content
print(f"   {'✓' if dummy_cep else '✗'} cep package: {dummy_cep}")
print(f"   {'✓' if dummy_sep else '✗'} sep package: {dummy_sep}")
if not (dummy_cep and dummy_sep):
    critical_issues.append("DummyDummyMiddleware missing")

# SUMMARY
print("\n" + "=" * 70)
if critical_issues:
    print("❌ CRITICAL ISSUES FOUND:")
    for issue in critical_issues:
        print(f"   • {issue}")
    print("\n⛔ CANNOT APPROVE COMPLETION")
else:
    print("✅ ALL CRITICAL REQUIREMENTS VERIFIED")
    print("✅ COMPLETION APPROVED")
print("=" * 70)
