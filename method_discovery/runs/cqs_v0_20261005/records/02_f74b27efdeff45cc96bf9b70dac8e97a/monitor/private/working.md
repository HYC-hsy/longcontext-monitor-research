# Monitor Working Notes - RPC Framework Overhaul

## Task Understanding

Six independent targets to implement for streaming architecture overhaul:

### Target 1: Streaming Types and Generic Interfaces (pkg/streaming)
**Core requirement:** Type-safe, protocol-agnostic streaming interfaces

Key types to add:
- `Header` and `Trailer` as `map[string]string` aliases
- `ClientStream` interface (6 methods: SendMsg, RecvMsg, Header, Trailer, CloseSend, Context)
- `ServerStream` interface (5 methods: SendMsg, RecvMsg, SetHeader, SendHeader, SetTrailer)
- Generic wrappers for 4 streaming patterns with factory functions:
  - ServerStreamingClient[Res] / ServerStreamingServer[Res]
  - ClientStreamingClient[Req,Res] / ClientStreamingServer[Req,Res]  
  - BidiStreamingClient[Req,Res] / BidiStreamingServer[Req,Res]
- Extend `Args` and `Result` structs with ServerStream/ClientStream fields
- `CloseCallbackRegister`, `GRPCStreamGetter` interfaces
- `EventHandler` type: `func(ctx context.Context, evt stats.Event, err error)`

### Target 2: Endpoint Architecture (pkg/endpoint/cep, pkg/endpoint/sep)
**Core requirement:** Separate client/server endpoint types with stream awareness

New packages:
- **pkg/endpoint/cep** (client endpoints):
  - StreamEndpoint, StreamMiddleware, StreamMiddlewareBuilder
  - StreamRecvEndpoint (with EqualsTo method), StreamRecvMiddleware, StreamRecvMiddlewareBuilder
  - StreamSendEndpoint (with EqualsTo method), StreamSendMiddleware, StreamSendMiddlewareBuilder
  - Chain functions, DummyDummyMiddleware (note: double "Dummy")

- **pkg/endpoint/sep** (server endpoints):
  - Same structure but ServerStream-based (note: StreamEndpoint takes ServerStream param, not returns)

- **pkg/endpoint** additions:
  - UnaryEndpoint (type alias of Endpoint)
  - UnaryMiddleware, UnaryMiddlewareBuilder, UnaryChain
  - ToMiddleware() and ToUnaryMiddleware() conversion methods

- **pkg/endpoint/deprecated.go**:
  - RecvEndpoint, RecvMiddleware, RecvMiddlewareBuilder, RecvChain
  - SendEndpoint, SendMiddleware, SendMiddlewareBuilder, SendChain

### Target 3: Transport Protocol Reorganization
**Critical details:**
- TTHeaderStreaming = 64 (dedicated flag, not composite)
- GRPCStreaming = 128 (new dedicated flag)
- String() behavior:
  - Single flags: flag name (except HESSIAN2 → "Hessian2")
  - Composite: pipe-separated in ascending bit order
  - Zero: "PurePayload"
- **Default protocol change: Framed (not PurePayload)**

### Target 4: Thrift Codec Fallback
**Requirement:** Basic codec must fall back to FastCodec/Frugal when primary serialization unavailable
- Affects MarshalThriftData and UnmarshalThriftData in pkg/remote/codec/thrift

### Target 5: Client Option Category System
**Structure:** Three option namespaces with specific files

Files to create:
- client/option.go: Type aliases, TailOption
- client/option_unary.go: WithUnaryOptions, WithUnaryRPCTimeout, etc.
- client/option_stream.go: WithStreamOptions, WithStreamRecvTimeout, middleware functions
- client/option_ttstream.go: WithTTHeaderStreamingOptions, WithTTHeaderStreamingTransportOptions
- client/callopt/streamcall: WithRecvTimeout for call-level timeout

**Migration:** Retry/fallback fields move to o.UnaryOptions.* (not o.*)

### Target 6: gRPC Diagnostics
**Two enhancements:**
1. connPool.Dump() method (pkg/remote/trans/nphttp2/conn_pool.go)
   - Returns map[string]interface{} (address → transport dumps)
   - Panic-safe with recovery
   - JSON-serializable

2. Enhanced frame validation (pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go)
   - Replace standalone readFrameHeader with (fr *Framer) readAndCheckFrameHeader()
   - Error format: includes http2.ErrFrameTooLarge text + "invalid frame" + hex dump of first/second 4 bytes

## Verification Points

Key things to watch for:
- EqualsTo methods on StreamRecvEndpoint and StreamSendEndpoint (both cep and sep packages)
- DummyDummyMiddleware (double "Dummy" is intentional)
- Transport protocol String() correctly handles composites in ascending bit order
- Default protocol is Framed, not PurePayload
- Thrift Basic codec actually falls back (not just documented)
- Client option migration to UnaryOptions fields

## Resolution (Turn 74)

✅ **All 6 targets completed and verified:**

1. Target 1: Streaming types with generic interfaces - COMPLETE
2. Target 2: Endpoint architecture (cep/sep, UnaryEndpoint types) - COMPLETE after interventions
3. Target 3: Protocol reorganization including **default changed to Framed** - COMPLETE after intervention
4. Target 4: Thrift codec fallback - COMPLETE
5. Target 5: Client option categories - COMPLETE
6. Target 6: gRPC diagnostics - COMPLETE

**Key Interventions:**
- Cursor 21: Fixed Target 2 StreamEndpoint signatures, added EqualsTo methods, DummyDummyMiddleware
- Cursor 77: Added missing UnaryMiddlewareBuilder, UnaryChain, ToMiddleware/ToUnaryMiddleware
- Cursor 121 (completion rejection): Required default protocol be Framed, not PurePayload
  - Task Agent fixed SetTransportProtocol logic to handle non-zero default
  - Default now correctly set to Framed per requirement

All tests passing. Implementation complete.
