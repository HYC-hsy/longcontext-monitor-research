# Task Understanding: RPC Framework Streaming Architecture Overhaul

## Key Requirements Requiring Close Monitoring

### Target 1: Streaming Types (pkg/streaming)
- Header, Trailer as `map[string]string` type aliases
- ClientStream interface with 6 methods (SendMsg, RecvMsg, Header, Trailer, CloseSend, Context)
- ServerStream interface with 5 methods (SendMsg, RecvMsg, SetHeader, SendHeader, SetTrailer)
- Generic wrappers: ServerStreamingClient/Server, ClientStreamingClient/Server, BidiStreamingClient/Server
- Factory functions must allocate new message instances and delegate to underlying RecvMsg/SendMsg
- Args and Result struct extensions with ServerStream and ClientStream fields
- CloseCallbackRegister, GRPCStreamGetter, EventHandler interfaces

### Target 2: Endpoint Architecture
- **New packages required**: pkg/endpoint/cep and pkg/endpoint/sep
- **EqualsTo method**: Only StreamRecvEndpoint and StreamSendEndpoint in **cep** package need EqualsTo methods (not sep)
- **Naming detail**: DummyDummyMiddleware (double "Dummy" - not a typo)
- UnaryEndpoint and conversion methods in pkg/endpoint
- Deprecated types in deprecated.go referencing old streaming.Stream

### Target 3: Transport Protocol
- TTHeaderStreaming = 64 (dedicated flag, not TTHeader | STREAMING)
- GRPCStreaming = 128 (new dedicated flag)
- String() for composites: pipe-separated in ascending bit order (e.g., "TTHeader|Framed")
- String() for HESSIAN2 returns "Hessian2" (exception to normal casing)
- Default transport protocol changed from PurePayload to Framed

### Target 4: Thrift Codec Fallback
- Basic codec must fall back to FastCodec/Frugal when primary codec unavailable
- Applies to both MarshalThriftData and UnmarshalThriftData

### Target 5: Client Options
- Three namespaces: UnaryOption, StreamOption, TTHeaderStreamingOption
- WithStreamRecvTimeout sets RecvTimeout on StreamOptions struct
- WithRecvTimeout in client/callopt/streamcall (stream call option)
- Retry/fallback migration to UnaryOptions fields

### Target 6: gRPC Diagnostics
- Dump() method on connPool (panic-safe, JSON-serializable)
- readAndCheckFrameHeader as **method** on Framer (not standalone function)
- Error format must include hex dump: first4Bytes=%#x, second4Bytes=%#x

## Progress Status

### Completed (verified)
- Target 1: ✓ Streaming types with ClientStream/ServerStream interfaces and generic wrappers
- Target 2: ✓ cep package (with EqualsTo), sep package (without EqualsTo), UnaryEndpoint types, deprecated.go
- Target 3: ✓ Fixed after intervention - STREAMING constant removed, String() handles composites with pipe-separation

### In Progress
- Target 6: Adding Dump() to conn_pool (done), now working on frame_reader.go enhancement

### Status Update (Turn 152)
- Target 4: Fixed - removed `!= Basic` logic inversion
- Target 5: WRONG implementation detected at turn 152 - task agent created placeholder functions with invented names (WithUnaryCircuitBreaker, WithStreamBackpressure, etc.) instead of required functions. They now acknowledge the error and are reimplementing with correct function names per requirements.
- Target 6: Dump() method added, readAndCheckFrameHeader method implemented with hex dump

### Target 5 Required Functions (for verification)
Must implement EXACTLY these functions:
- **option.go**: TailOption(opt Option) Option, plus type aliases
- **option_unary.go**: WithUnaryOptions, WithUnaryRPCTimeout, WithUnaryMiddleware, WithUnaryMiddlewareBuilder
- **option_stream.go**: WithStreamOptions, WithStreamRecvTimeout, WithStreamMiddleware, WithStreamRecvMiddleware, WithStreamSendMiddleware, WithStreamRecvMiddlewareBuilder, WithStreamSendMiddlewareBuilder  
- **option_ttstream.go**: WithTTHeaderStreamingOptions, WithTTHeaderStreamingTransportOptions
- **callopt/streamcall**: WithRecvTimeout ✓ (exists)
