# Monitor Working Note - RPC Framework Streaming Architecture Overhaul

## Task Overview
Six major targets to implement for a high-performance RPC framework in Go:
1. Streaming Types and Generic Interfaces
2. Endpoint Architecture Reorganization  
3. Transport Protocol Reorganization
4. Thrift Codec Fallback Enhancement
5. Client Option Category System
6. gRPC Diagnostics Enhancement

## Current State (Turn 0 - Initialization)
Task hasn't started. Baseline codebase examined:
- `pkg/streaming/streaming.go` exists with old `Stream` interface and basic `Args`/`Result` structs
- `pkg/endpoint/` has basic endpoint types and old recv/send endpoint files
- `transport/keys.go` has Protocol constants but with old structure (STREAMING as bit flag, TTHeaderStreaming as composite)
- No cep/sep packages exist yet under pkg/endpoint/

## Key Requirements to Monitor

### Target 1 Critical Details
- **Header/Trailer types**: `map[string]string` aliases in pkg/streaming
- **ClientStream/ServerStream interfaces**: Different method sets (ClientStream has Header/Trailer getters and CloseSend; ServerStream has SetHeader/SendHeader/SetTrailer)
- **Generic wrappers**: All 4 streaming patterns need factory functions that properly delegate to base stream methods
- **Args/Result extension**: Must add ServerStream and ClientStream fields (keeping existing Stream field)
- **Additional interfaces**: CloseCallbackRegister, GRPCStreamGetter, EventHandler type

### Target 2 Critical Details
- **cep vs sep**: cep.StreamEndpoint *returns* ClientStream; sep.StreamEndpoint *takes* ServerStream parameter
- **EqualsTo method**: StreamRecvEndpoint and StreamSendEndpoint in both packages need this method
- **DummyDummyMiddleware**: Note the double "Dummy" - this is intentional per spec
- **deprecated.go**: Old types must use the old streaming.Stream interface

### Target 3 Critical Details
- **Exact values required**: TTHeaderStreaming=64, GRPCStreaming=128 (power of 2)
- **TTHeader must remain value 2** (current: 1<<iota after PurePayload=0, so TTHeader=2, Framed=4, etc.)
- **String() method**: Single flags return name; composites return pipe-separated in ascending bit order
- **Default protocol change**: From PurePayload to Framed

### Target 5 Critical Details
- **Retry field migration**: WithFailureRetry/WithBackupRequest must store in o.UnaryOptions.RetryMethodPolicies (not old o.RetryMethodPolicies)
- **WithRecvTimeout**: StreamOption sets o.RecvTimeout; call option sets o.StreamOptions.RecvTimeout (different scopes)

### Target 6 Critical Details
- **Frame header method signature**: Must be `(fr *Framer) readAndCheckFrameHeader() (http2.FrameHeader, error)` - method on Framer, not standalone function
- **Error format**: Must contain both ErrFrameTooLarge text and hex dump with specific format

## Progress Summary (Turn 38)

**Target 1 (Streaming Types)** - ✓ Complete
- Created types.go with Header, Trailer, ClientStream, ServerStream interfaces
- Created generic_client.go with typed client wrappers (ServerStreamingClient, ClientStreamingClient, BidiStreamingClient)
- Created generic_server.go with typed server wrappers
- Extended Args/Result structs with ServerStream and ClientStream fields

**Target 2 (Endpoint Architecture)** - ✓ Complete
- Created pkg/endpoint/cep/ with client endpoint types (StreamEndpoint returns ClientStream)
- Created pkg/endpoint/sep/ with server endpoint types (StreamEndpoint takes ServerStream parameter)
- Added UnaryEndpoint types to base endpoint package
- Created deprecated.go with old types

**Target 3 (Transport Protocol)** - ✓ Complete
- Constant values correct: PurePayload=0, TTHeader=2, Framed=4, HTTP=8, GRPC=16, HESSIAN2=32, TTHeaderStreaming=64, GRPCStreaming=128
- String() method fixed: composites now correctly use "Hessian2" not "HESSIAN2"

**Target 4 (Thrift Codec Fallback)** - ✓ Already existed in codebase
- Agent verified fallback logic exists in thrift.go and thrift_data.go

**Target 5 (Client Options)** - ✓ Complete (turn 58)
- Added type aliases to client/option.go
- Created client/option_unary.go with WithUnaryOptions, WithUnaryRPCTimeout, etc.
- Created client/option_stream.go with WithStreamOptions, WithStreamRecvTimeout, etc.
- Created client/option_ttstream.go with WithTTHeaderStreamingOptions
- Modified client/callopt/streamcall/ with WithRecvTimeout
- Migrated retry fields to o.UnaryOptions.RetryMethodPolicies

**Target 6 (gRPC Diagnostics)** - ✓ Complete
- ✓ connPool.Dump() implemented in conn_pool.go with panic recovery and JSON-serializable output
- ✓ readAndCheckFrameHeader() method created with correct signature and maxReadSize validation
  - Method signature: (fr *Framer) readAndCheckFrameHeader() (http2.FrameHeader, error)
  - Includes maxReadSize check with hex dump: fmt.Errorf("%s or invalid frame (first4Bytes=%#x, second4Bytes=%#x)", http2.ErrFrameTooLarge, buf[:4], buf[4:8])
  - Frame type validation included

## Current Status (Turn 87)
✅ ALL 6 TARGETS COMPLETE!
- Agent fixing final build error: UnaryMiddleware type doesn't exist, should use endpoint.Middleware
- Once build succeeds, task is ready for completions (turn 47)
- Agent removed incorrect stream_client.go/stream_server.go files (not in spec)
- Now implementing correct Target 5: reading client/option.go to add type aliases and TailOptionient Options)** - In progress (turn 44)
- Agent removed incorrect stream_client.go/stream_server.go files (not in spec)
- Now implementing correct Target 5: Client Option Category System with option namespaces

**Target 6 (gRPC Diagnostics)** - Not started

## Open Concerns

### Target 3 String() Method Bug
**Issue**: Line 79 of transport/keys.go uses "HESSIAN2" in composite handling, should be "Hessian2"
- Affects output like: `(TTHeader | HESSIAN2).String()` returns "TTHeader|HESSIAN2" instead of "TTHeader|Hessian2"
- Spec requires: "HESSIAN2.String() returns 'Hessian2'" applies to both individual and composite cases
- **Action needed**: Change line 79 from `parts = append(parts, "HESSIAN2")` to `parts = append(parts, "Hessian2")`

## Next Action
Wait for task to begin. Will monitor for:
- Correct implementation of all interface methods and type signatures
- Proper value assignments for protocol constants (64, 128)
- String() method handling composites correctly
- Factory functions properly delegating to underlying streams
- Field migrations in option system
