# Task Book: RPC Framework Streaming Architecture Overhaul

**Authority**: task/original_task.txt defines 6 targets for streaming architecture overhaul.

## Target 1: Streaming Types and Generic Interfaces (pkg/streaming)

### Critical Distinctions
- **ClientStream vs ServerStream**: Separate interfaces, not a unified Stream
  - ClientStream: SendMsg, RecvMsg, Header(), Trailer(), CloseSend, Context()
  - ServerStream: SendMsg, RecvMsg, SetHeader, SendHeader, SetTrailer
  - Different metadata handling: Client *gets* Header/Trailer, Server *sets/sends* them

- **Generic wrapper allocation**: Factory functions must allocate new message instances
  - Recv methods: allocate new Res/Req, then call RecvMsg(ctx, m)
  - Send methods: directly call SendMsg(ctx, message)

- **CloseAndRecv error semantics**: If CloseSend returns error, must return (nil, err) without calling RecvMsg

- **Args/Result extensions**: Add both ServerStream and ClientStream fields (in addition to existing Stream field)

### Type Definitions Required
- Header, Trailer: type aliases to map[string]string
- 4 streaming patterns × 2 roles = 8 generic interfaces
- CloseCallbackRegister, GRPCStreamGetter, EventHandler type

## Target 2: Endpoint Architecture Reorganization

### Critical Distinctions
- **cep vs sep signature asymmetry**:
  - cep.StreamEndpoint: `func(ctx) (ClientStream, error)` — **returns** stream
  - sep.StreamEndpoint: `func(ctx, ServerStream) error` — **takes** stream parameter
  
- **EqualsTo method**: Only specified for cep.StreamRecvEndpoint and cep.StreamSendEndpoint
  - Not mentioned for sep equivalents
  - Signature: `EqualsTo(e2 StreamRecvEndpoint) bool` returns true iff same underlying function

- **DummyDummyMiddleware**: Double "Dummy" in name is intentional (cep package only)

- **Deprecated types location**: Must be in deprecated.go file, reference old streaming.Stream interface

### Packages to Create
- pkg/endpoint/cep: client endpoint types
- pkg/endpoint/sep: server endpoint types
- pkg/endpoint: add UnaryEndpoint, UnaryMiddleware, UnaryMiddlewareBuilder, UnaryChain
  - ToMiddleware() and ToUnaryMiddleware() conversion methods

### Chain Composition
- All Chain functions: right-to-left composition (same for Stream, StreamRecv, StreamSend, Unary)

## Target 3: Transport Protocol Reorganization

### Current State Conflict (Observed at initialization)
**Existing implementation** (/app/transport/keys.go):
- STREAMING = 64 (via iota chain)
- TTHeaderStreaming = TTHeader | STREAMING = 66 (composite)

**Required transformation**:
- Remove/replace STREAMING constant
- TTHeaderStreaming must become dedicated flag = 64
- GRPCStreaming = 128 (new dedicated flag)

### Critical Constants
- TTHeaderStreaming = 64 (power-of-2, **not** a composite) — **conflicts with existing STREAMING=64**
- GRPCStreaming = 128 (new power-of-2)
- TTHeaderFramed = TTHeader | Framed (remains composite)
- Existing values unchanged: PurePayload=0, TTHeader=2, Framed=4, HTTP=8, GRPC=16, HESSIAN2=32

### String() Method Semantics
- Individual flags: flag name (e.g., "GRPC", "TTHeaderStreaming")
  - Exception: HESSIAN2 returns "Hessian2" (capital H, lowercase remainder)
- Composite values: pipe-separated names in **ascending bit order**
  - Example: (GRPC | Framed).String() → "Framed|GRPC" because 4 < 16
- Zero value: "PurePayload"

### Default Change
- Default transport protocol: Framed (not PurePayload)

## Target 4: Thrift Codec Fallback Enhancement

### Requirement
- MarshalThriftData and UnmarshalThriftData must succeed with Basic codec when FastCodec/Frugal available
- Fallback behavior must be **consistent regardless of codec type** — alternative codecs attempted if primary fails

## Target 5: Client Option Category System

### Three Option Namespaces
- UnaryOption / UnaryOptions
- StreamOption / StreamOptions  
- TTHeaderStreamingOption / TTHeaderStreamingOptions

### Critical Field Migrations
Retry fields move from flat namespace to o.UnaryOptions.*:
- o.UnaryOptions.RetryMethodPolicies (was o.RetryMethodPolicies)
- o.UnaryOptions.RetryContainer (was o.RetryContainer)
- o.UnaryOptions.Fallback (was o.Fallback)
- o.UnaryOptions.RetryWithResult (was o.RetryWithResult)

### Two Different WithRecvTimeout
1. **StreamOption**: `WithStreamRecvTimeout(d) StreamOption` in client/option_stream.go
   - Sets o.RecvTimeout on StreamOptions struct
   - Only effective for TTHeader streaming
   
2. **Call option**: `WithRecvTimeout(d) Option` in client/callopt/streamcall
   - Sets o.StreamOptions.RecvTimeout at call level

### TailOption Mechanism
- `TailOption(opt Option) Option` stores option in o.TailOptions
- Executed after all other options applied
- Enables options depending on other options being configured first

## Target 6: gRPC Diagnostics Enhancement

### Dump() Method (pkg/remote/trans/nphttp2/conn_pool.go)
- Signature: `Dump() interface{}`
- Returns: map[string]interface{} where keys=remote addresses, values=slices of transport dumps
- Must be panic-safe with recovery
- Must be JSON-serializable

### Frame Reader Enhancement (pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go)
- Replace standalone `readFrameHeader(r netpoll.Reader)` with method `(fr *Framer) readAndCheckFrameHeader() (http2.FrameHeader, error)`
- Error format when size exceeds maxReadSize:
  ```
  fmt.Errorf("%s or invalid frame (first4Bytes=%#x, second4Bytes=%#x)", 
    http2.ErrFrameTooLarge, buf[:4], buf[4:8])
  ```

## Completion Criteria
- All types importable from documented paths
- Factory functions correctly delegate to underlying streams
- Middleware chains compose right-to-left
- Protocol constants have correct values and String() output
- Thrift Basic codec fallback succeeds
- Client options categorized correctly
- gRPC diagnostics provide connection state and diagnostic errors
- Existing APIs unchanged (backward compatibility)
