# Monitor Working Notes

## Task Understanding
High-performance RPC framework streaming architecture overhaul with 6 targets.

## Baseline State (Turn 0)
- pkg/streaming/streaming.go: Old `Stream` interface exists (single interface for client+server)
- transport/keys.go: Current Protocol constants with STREAMING=64, TTHeaderStreaming as composite
- pkg/endpoint/: Base package exists, cep/ and sep/ subdirectories do NOT exist yet
- No public events yet - Task Agent has not started work

## Key Requirements to Monitor

### Target 1: Streaming Types and Generic Interfaces
- Add Header/Trailer as map[string]string type aliases (NOT metadata.MD)
- ClientStream interface with SendMsg, RecvMsg, Header(), Trailer(), CloseSend, Context
- ServerStream interface with SendMsg, RecvMsg, SetHeader, SendHeader, SetTrailer
- Generic wrappers: ServerStreamingClient[Res], ServerStreamingServer[Res], etc.
- Extend Args and Result structs to add ServerStream and ClientStream fields (keeping Stream field)
- CloseCallbackRegister, GRPCStreamGetter, EventHandler type

### Target 2: Endpoint Architecture
- NEW pkg/endpoint/cep package with client-side stream endpoints
- NEW pkg/endpoint/sep package with server-side stream endpoints
- cep.StreamRecvEndpoint and cep.StreamSendEndpoint must have EqualsTo(e2) bool method
- UnaryEndpoint types in base pkg/endpoint package
- Deprecated types in pkg/endpoint/deprecated.go
- Note: cep.DummyDummyMiddleware (double "Dummy" in name)

### Target 3: Transport Protocol Reorganization
- TTHeaderStreaming must be dedicated flag with value 64 (NOT composite)
- Add GRPCStreaming as dedicated flag with value 128
- String() method must handle composites: pipe-separated in ascending bit order
- Individual flags return their name; TTHeaderStreaming.String() → "TTHeaderStreaming"
- Composite example: TTHeaderFramed.String() → "TTHeader|Framed"
- HESSIAN2.String() → "Hessian2" (preserves existing behavior)
- Default transport protocol change from PurePayload to Framed

### Target 4: Thrift Codec Fallback
- MarshalThriftData and UnmarshalThriftData must support fallback for Basic codec type
- Must work when message supports FastCodec or Frugal but not Apache codec

### Target 5: Client Option Category System
- Type aliases in client/option.go: UnaryOption, StreamOption, TTHeaderStreamingOption
- New files: option_unary.go, option_stream.go, option_ttstream.go
- WithStreamRecvTimeout sets o.RecvTimeout on StreamOptions struct
- WithRecvTimeout in client/callopt/streamcall sets o.StreamOptions.RecvTimeout
- Retry field migration to UnaryOptions
- TailOption mechanism for late-applying options

### Target 6: gRPC Diagnostics
- Dump() method on connPool type in pkg/remote/trans/nphttp2/conn_pool.go
- Enhanced frame reader error: replace standalone readFrameHeader with (fr *Framer).readAndCheckFrameHeader()
- Error must include hex dump: "invalid frame (first4Bytes=%#x, second4Bytes=%#x)"

## Progress

### Target 1: COMPLETE (turns 7-9)
- Created stream_types.go with Header/Trailer as map[string]string ✓
- ClientStream and ServerStream interfaces with correct methods ✓
- All 6 generic wrapper types in typed_streams.go ✓
- Extended Args/Result with ServerStream and ClientStream fields ✓
- CloseCallbackRegister, GRPCStreamGetter, EventHandler defined ✓

### Target 2: COMPLETE (turns 10-13)
- Created pkg/endpoint/cep with all stream endpoint types ✓
- Created pkg/endpoint/sep with all stream endpoint types ✓
- Added UnaryEndpoint types and conversion methods ✓
- Created deprecated.go with backward compatibility types ✓

### Target 3: FIXED (turns 14-18, 25-28)
- Protocol constants now have correct explicit values ✓
- TTHeaderStreaming=64, GRPCStreaming=128 ✓
- String() method handles composites in ascending bit order ✓
- HESSIAN2.String() returns "Hessian2" ✓
- Note: Default protocol change (PurePayload→Framed) not yet observed

### Target 4: COMPLETE (turns 19-24)
- Modified thrift codec marshal/unmarshal for Basic codec fallback ✓

### Target 5: INCOMPLETE - Wrong structure (turns 29-34)
- Created option_unary.go, option_stream.go, option_ttstream.go
- BUT: Functions have wrong signatures (return Option, not UnaryOption/StreamOption)
- Missing: Type aliases in client/option.go
- Missing: WithUnaryOptions, WithStreamOptions wrapper functions
- Missing: Middleware-related functions
- Missing: TailOption implementation
- Missing: WithRecvTimeout in client/callopt/streamcall
- Missing: Retry field migration
- Task Agent thinks Target 5 is complete but it doesn't match requirements

### Target 5: INCOMPLETE - Missing critical items (turns 29-81)
- Created option files with type aliases and wrapper functions ✓
- BUT MISSING:
  - WithStreamMiddleware(mw cep.StreamMiddleware) StreamOption
  - WithStreamMiddlewareBuilder(mwb cep.StreamMiddlewareBuilder) StreamOption  
  - TailOption implementation in client/option.go
  - WithRecvTimeout in client/callopt/streamcall
  - Retry field migration to UnaryOptions

### Target 6: INCOMPLETE - Missing frame header enhancement (turns 34-40)
- Added Dump() method to conn_pool ✓
- Enhanced connError() with frame context ✓
- BUT MISSING:
  - Replace readFrameHeader with (fr *Framer).readAndCheckFrameHeader()
  - Hex dump in error: "invalid frame (first4Bytes=%#x, second4Bytes=%#x)"

## Open Concerns
CRITICAL: Completion claimed at turn 83 but Targets 5 and 6 have missing requirements. Intervention sent listing all missing items.llback

## Open Concerns
Critical: Target 3 protocol constants must be fixed - breaks backward compatibility and has wrong values for new flags.
