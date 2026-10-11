# Task Book: RPC Framework Streaming Architecture Overhaul

## Mission
Overhaul streaming architecture for a Go RPC framework across 6 targets. Task authority: task/original_task.txt

## Critical Requirements & Constraints

### Target 1: Streaming Types and Generic Interfaces (pkg/streaming)

**Core Separation**: ClientStream vs ServerStream have DIFFERENT method sets
- ClientStream: SendMsg, RecvMsg, Header(), Trailer(), CloseSend, Context()
- ServerStream: SendMsg, RecvMsg, SetHeader, SendHeader, SetTrailer (NO CloseSend, NO Header/Trailer getters)

**Type Aliases**: Header and Trailer are `map[string]string` type aliases (not struct types)

**Generic Wrappers**: 4 streaming patterns with specific method signatures:
- ServerStreamingClient[Res]: embeds ClientStream, adds `Recv(ctx) (*Res, error)`
- ServerStreamingServer[Res]: embeds ServerStream, adds `Send(ctx, *Res) error`
- ClientStreamingClient[Req,Res]: Send, CloseAndRecv (CloseAndRecv must call CloseSend THEN RecvMsg; if CloseSend errors, return (nil, err))
- ClientStreamingServer[Req,Res]: Recv, SendAndClose
- BidiStreamingClient[Req,Res]: Send, Recv
- BidiStreamingServer[Req,Res]: Recv, Send

**Factory Pattern**: Each generic wrapper needs NewXxx factory function that allocates message instances and delegates to base stream

**Args/Result Extension**: Extend BOTH Args and Result structs with ServerStream and ClientStream fields (in addition to existing Stream field)

**Additional Interfaces**:
- CloseCallbackRegister: single method `RegisterCloseCallback(cb func(error))`
- GRPCStreamGetter: single method `GetGRPCStream() Stream` (where Stream is OLD interface)
- EventHandler type: `func(ctx context.Context, evt stats.Event, err error)` using pkg/stats from THIS codebase

### Target 2: Endpoint Architecture (pkg/endpoint/cep, pkg/endpoint/sep)

**Package Separation**: cep = client endpoints, sep = server endpoints

**Signature Distinction**:
- cep.StreamEndpoint: `func(ctx) (streaming.ClientStream, error)` - RETURNS a stream
- sep.StreamEndpoint: `func(ctx, streaming.ServerStream) error` - TAKES a stream parameter

**EqualsTo Method**: StreamRecvEndpoint and StreamSendEndpoint in BOTH cep and sep must have `EqualsTo(e2 XxxEndpoint) bool` method that returns true iff both reference same underlying function

**Chain Composition**: All Chain functions (StreamChain, StreamRecvChain, StreamSendChain) compose right-to-left

**Special Middleware**: cep needs `DummyDummyMiddleware` (note: double "Dummy") that returns next unchanged

**Unary Endpoint (pkg/endpoint)**:
- UnaryEndpoint: new named type based on existing Endpoint type
- Conversion methods: `(mw UnaryMiddleware) ToMiddleware()` and `(mw Middleware) ToUnaryMiddleware()`
- UnaryChain also composes right-to-left

**Deprecated Types (pkg/endpoint/deprecated.go)**: RecvEndpoint, SendEndpoint and related types reference OLD streaming.Stream interface

### Target 3: Transport Protocol Reorganization (transport)

**Critical Value Requirements**:
- Existing values MUST NOT CHANGE: PurePayload=0, TTHeader=2, Framed=4, HTTP=8, GRPC=16, HESSIAN2=32
- TTHeaderStreaming: NEW dedicated flag = 64 (NOT composite)
- GRPCStreaming: NEW dedicated flag = 128
- TTHeaderFramed: remains COMPOSITE (TTHeader | Framed)

**String() Method Behavior**:
- Individual flags: return flag name (exception: HESSIAN2 → "Hessian2")
- TTHeaderStreaming.String() → "TTHeaderStreaming" (single name, NOT composition)
- Composite values: pipe-separated names in ASCENDING bit order (e.g., "TTHeader|Framed", "Framed|GRPC")
- Zero value: "PurePayload"

**Default Protocol Change**: Change default from PurePayload (0) to Framed (4)

### Target 4: Thrift Codec Fallback (pkg/remote/codec/thrift)

**Requirement**: MarshalThriftData and UnmarshalThriftData must succeed with Basic codec when message supports FastCodec or Frugal
- Fallback must work REGARDLESS of codec type
- If primary codec fails, must attempt alternative serialization codecs

### Target 5: Client Option Category System (client/)

**File Organization**:
- client/option.go: type aliases (UnaryOption, StreamOption, TTHeaderStreamingOption) and TailOption
- client/option_unary.go: WithUnaryOptions, WithUnaryRPCTimeout, WithUnaryMiddleware, WithUnaryMiddlewareBuilder
- client/option_stream.go: WithStreamOptions, WithStreamRecvTimeout (sets o.RecvTimeout), stream middleware functions
- client/option_ttstream.go: WithTTHeaderStreamingOptions, WithTTHeaderStreamingTransportOptions

**TailOption**: Stores option in o.TailOptions for execution AFTER all other options applied

**Stream Call Option**: client/callopt/streamcall needs WithRecvTimeout that sets o.StreamOptions.RecvTimeout

**Retry Field Migration**: WithFailureRetry and WithBackupRequest must store in o.UnaryOptions.RetryMethodPolicies (NOT old o.RetryMethodPolicies)
- WithRetryContainer → o.UnaryOptions.RetryContainer
- WithFallback → o.UnaryOptions.Fallback
- WithSpecifiedResultRetry → o.UnaryOptions.RetryWithResult

### Target 6: gRPC Diagnostics (pkg/remote/trans/nphttp2)

**Connection Pool Dump (conn_pool.go)**:
- Add `Dump() interface{}` method to connPool type
- Returns `map[string]interface{}` where keys=remote addresses, values=slices of transport dump results
- Must be panic-safe with recovery and error logging
- Result must be JSON-serializable

**Frame Reader Enhancement (grpc/grpcframe/frame_reader.go)**:
- Replace standalone `readFrameHeader(r netpoll.Reader)` with method `(fr *Framer) readAndCheckFrameHeader() (http2.FrameHeader, error)`
- When frame size exceeds maxReadSize: error must contain BOTH "ErrFrameTooLarge" text AND "invalid frame" with hex dump
- Format: `fmt.Errorf("%s or invalid frame (first4Bytes=%#x, second4Bytes=%#x)", http2.ErrFrameTooLarge, buf[:4], buf[4:8])`

## Completion Criteria

All 6 targets must be complete:
1. All new types/interfaces importable from documented paths
2. Factory functions delegate correctly
3. Middleware chains compose right-to-left
4. Transport protocol constants have correct values and String() output
5. Thrift codec fallback succeeds for Basic codec
6. Client options correctly categorized into namespaces
7. gRPC diagnostics provide connection state and diagnostic errors
8. Backward compatibility maintained

## Investigation Notes

Environment: Offline, no internet/reference solutions. Repository at /app.

Current workspace state (turn 0):
- pkg/streaming exists (has streaming.go and other files)
- pkg/endpoint exists (has endpoint.go, recv_endpoint.go, send_endpoint.go)
- pkg/endpoint/cep does NOT exist yet
- pkg/endpoint/sep does NOT exist yet
- transport exists (has keys.go)
- pkg/remote/codec/thrift exists
- client exists (has option.go and other files)
- pkg/remote/trans/nphttp2 exists (has conn_pool.go likely)
- pkg/remote/trans/nphttp2/grpc/grpcframe exists (has frame_reader.go)
