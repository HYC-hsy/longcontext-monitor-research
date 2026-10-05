
# Final root verification against all 6 targets
print("=" * 70)
print("ROOT COMPLETION VERIFICATION - ALL 6 TARGETS")
print("=" * 70)

all_complete = True
issues = []

# Target 1: Streaming Types (9 requirements)
with open('/app/pkg/streaming/streaming.go', 'r') as f:
    t1 = f.read()
t1_ok = all([
    'type Header map[string]string' in t1,
    'type Trailer map[string]string' in t1,
    'type ClientStream interface' in t1,
    'type ServerStream interface' in t1,
    all(x in t1 for x in ['ServerStreamingClient', 'ServerStreamingServer', 'ClientStreamingClient', 'ClientStreamingServer', 'BidiStreamingClient', 'BidiStreamingServer']),
    'NewServerStreamingClient' in t1 and 'NewBidiStreamingClient' in t1,
    'ServerStream ServerStream' in t1 and 'ClientStream ClientStream' in t1,
    'type CloseCallbackRegister interface' in t1,
    'type GRPCStreamGetter interface' in t1,
    'type EventHandler func' in t1
])
print(f"\n{'✓' if t1_ok else '✗'} Target 1: Streaming Types - {'COMPLETE' if t1_ok else 'INCOMPLETE'}")
if not t1_ok: 
    issues.append("Target 1 incomplete")
    all_complete = False

# Target 2: Endpoint Architecture (11 requirements)
with open('/app/pkg/endpoint/cep/endpoint.go', 'r') as f:
    cep = f.read()
with open('/app/pkg/endpoint/sep/endpoint.go', 'r') as f:
    sep = f.read()
with open('/app/pkg/endpoint/endpoint.go', 'r') as f:
    ep = f.read()

t2_cep_ok = all([
    'func(ctx context.Context) (st streaming.ClientStream, err error)' in cep,
    'func (e StreamRecvEndpoint) EqualsTo' in cep,
    'func (e StreamSendEndpoint) EqualsTo' in cep,
    'func DummyDummyMiddleware' in cep
])
t2_sep_ok = 'func(ctx context.Context, st streaming.ServerStream) (err error)' in sep
t2_ep_ok = all([
    'type UnaryMiddlewareBuilder' in ep,
    'func UnaryChain' in ep,
    'func (mw UnaryMiddleware) ToMiddleware' in ep,
    'func (mw Middleware) ToUnaryMiddleware' in ep
])
t2_ok = t2_cep_ok and t2_sep_ok and t2_ep_ok
print(f"{'✓' if t2_ok else '✗'} Target 2: Endpoint Architecture - {'COMPLETE' if t2_ok else 'INCOMPLETE'}")
if not t2_cep_ok:
    issues.append("Target 2 cep package issues")
    all_complete = False
if not t2_sep_ok:
    issues.append("Target 2 sep.StreamEndpoint signature wrong")
    all_complete = False
if not t2_ep_ok:
    issues.append("Target 2 UnaryEndpoint types missing")
    all_complete = False

# Target 3: Transport Protocol (4 requirements - CRITICAL)
with open('/app/transport/keys.go', 'r') as f:
    trans = f.read()
with open('/app/pkg/rpcinfo/rpcconfig.go', 'r') as f:
    rpc = f.read()

t3_ok = all([
    'TTHeaderStreaming Protocol = 64' in trans,
    'GRPCStreaming Protocol = 128' in trans or 'GRPCStreaming     Protocol = 128' in trans,
    'parts = append' in trans,  # String() handles composites
    'transportProtocol = transport.Framed' in rpc and 'initialize()' in rpc  # CRITICAL: default is Framed
])
print(f"{'✓' if t3_ok else '✗'} Target 3: Transport Protocol - {'COMPLETE' if t3_ok else 'INCOMPLETE'}")
if not t3_ok:
    issues.append("Target 3 incomplete (check default protocol)")
    all_complete = False

# Target 4, 5, 6: Quick verification
with open('/app/pkg/remote/codec/thrift/thrift.go', 'r') as f:
    thrift = f.read()
t4_ok = 'TTHeaderStreaming' in thrift
print(f"{'✓' if t4_ok else '✗'} Target 4: Thrift Codec Fallback - {'COMPLETE' if t4_ok else 'INCOMPLETE'}")
if not t4_ok:
    all_complete = False

with open('/app/client/option.go', 'r') as f:
    opts = f.read()
t5_ok = all(x in opts for x in ['UnaryOption', 'StreamOption', 'TTHeaderStreamingOption'])
print(f"{'✓' if t5_ok else '✗'} Target 5: Client Option Categories - {'COMPLETE' if t5_ok else 'INCOMPLETE'}")
if not t5_ok:
    all_complete = False

with open('/app/pkg/remote/trans/nphttp2/grpc/transport.go', 'r') as f:
    grpc = f.read()
t6_ok = ('func (s *Stream) Dump()' in grpc or 'func (s *stream) Dump()' in grpc) and 'streamID' in grpc
print(f"{'✓' if t6_ok else '✗'} Target 6: gRPC Diagnostics - {'COMPLETE' if t6_ok else 'INCOMPLETE'}")
if not t6_ok:
    all_complete = False

print("\n" + "=" * 70)
if all_complete:
    print("✅ ALL 6 TARGETS VERIFIED COMPLETE")
    print("✅ READY FOR COMPLETION APPROVAL")
else:
    print("❌ INCOMPLETE - Issues found:")
    for issue in issues:
        print(f"   - {issue}")
print("=" * 70)
