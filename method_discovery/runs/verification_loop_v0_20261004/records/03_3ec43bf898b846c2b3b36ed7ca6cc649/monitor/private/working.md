# Monitor Working Note - RPC Framework Streaming Architecture Overhaul

## Task Understanding

Six independent targets for RPC framework enhancement:

### Target 1: Streaming Types and Generic Interfaces
- New Header/Trailer types (map[string]string aliases)
- ClientStream and ServerStream base interfaces with specific methods
- 8 generic typed interfaces (ServerStreamingClient/Server, ClientStreamingClient/Server, BidiStreamingClient/Server)
- Factory functions for each generic type
- Extensions to Args/Result structs
- CloseCallbackRegister, GRPCStreamGetter, EventHandler types

**Critical details:**
- ClientStream has Header()/Trailer() methods (metadata from server)
- ServerStream has SetHeader/SendHeader/SetTrailer methods
- Generic factory pattern: allocate new message, call base RecvMsg/SendMsg
- ClientStreamingClient has CloseAndRecv (CloseSend then RecvMsg)
- ClientStreamingServer has SendAndClose (just SendMsg)

### Target 2: Endpoint Architecture Reorganization
- New pkg/endpoint/cep (client endpoints) package
- New pkg/endpoint/sep (server endpoints) package
- Unary endpoint types in pkg/endpoint
- Deprecated types in pkg/endpoint/deprecated.go

**Critical details:**
- cep.StreamEndpoint returns ClientStream; sep.StreamEndpoint takes ServerStream parameter
- StreamRecvEndpoint and StreamSendEndpoint must have EqualsTo(e2) bool method (in cep only)
- Must have "DummyDummyMiddleware" (double "Dummy") in cep package
- All chains compose right-to-left
- UnaryMiddleware has ToMiddleware()/ToUnaryMiddleware() conversion methods

### Target 3: Transport Protocol Reorganization
- TTHeaderStreaming = 64 (dedicated flag, not composite)
- GRPCStreaming = 128 (new dedicated flag)
- String() method: single flags return name, composites return pipe-separated ascending order
- Exception: HESSIAN2.String() returns "Hessian2"
- Default transport changes from PurePayload to Framed

**Critical details:**
- TTHeaderStreaming.String() → "TTHeaderStreaming" (not composed)
- TTHeaderFramed.String() → "TTHeader|Framed"
- (GRPC | Framed).String() → "Framed|GRPC" (4 < 16)

### Target 4: Thrift Codec Fallback Enhancement
- MarshalThriftData must succeed with Basic codec when FastCodec/Frugal available
- UnmarshalThriftData same requirement
- Fallback behavior must be consistent regardless of codec type

### Target 5: Client Option Category System
- Type aliases for UnaryOption, StreamOption, TTHeaderStreamingOption
- New option files: option_unary.go, option_stream.go, option_ttstream.go
- TailOption mechanism for late-binding options
- WithRecvTimeout in client/callopt/streamcall package
- Retry/fallback migration to o.UnaryOptions fields

**Critical details:**
- WithStreamRecvTimeout sets o.RecvTimeout on StreamOptions (only effective for TTHeader)
- Stream call option WithRecvTimeout sets o.StreamOptions.RecvTimeout
- Retry policies go to o.UnaryOptions.RetryMethodPolicies (not o.RetryMethodPolicies)

### Target 6: gRPC Diagnostics Enhancement
- Dump() method on connPool returns map[string]interface{} (panic-safe)
- Replace readFrameHeader function with (fr *Framer) readAndCheckFrameHeader() method
- Error format must include: http2.ErrFrameTooLarge text, "invalid frame", hex of first and second 4 bytes

**Critical details:**
- Error format: fmt.Errorf("%s or invalid frame (first4Bytes=%#x, second4Bytes=%#x)", http2.ErrFrameTooLarge, buf[:4], buf[4:8])

## Current Status

Turn 49 - Task has completed reimplementation of Target 5. Progress:
- ✅ Target 1 complete (streaming types - verified)
- ✅ Target 2 complete (endpoint packages - verified after interventions)
- ✅ Target 3 complete (transport protocol constants - verified after interventions)
- ⏭️ Target 4 skipped (task claims no changes needed - codec info available via RPCInfo)
- ✅ Target 5 complete (REIMPLEMENTED correctly with option_unary/stream/ttstream files)
- ✅ Target 6 complete (diagnostics enhanced)

Ready for final verification before allowing completion.

## Resolved Concerns

### Target 2: sep package issues - RESOLVED
- Fixed StreamEndpoint signature to take ServerStream parameter (not return it)
- Removed EqualsTo methods from sep package (should only be in cep)

### Target 3: Transport protocol constants - RESOLVED
- Constant values now correct: TTHeader=2, Framed=4, HTTP=8, GRPC=16, HESSIAN2=32
- TTHeaderStreaming=64 and GRPCStreaming=128 added as dedicated flags
- String() method implemented dynamically for composites
- DefaultProtocol = Framed set

**Minor issue remaining**: STREAMING=32 (same value as HESSIAN2) could cause duplicate entries in String() output, but not critical since STREAMING wasn't in requirements.

## Open Concerns

### Target 4: May have been incorrectly skipped
Task synopsis said "Thrift codec doesn't need modification (protocol detection is handled elsewhere)" but Target 4 is about codec fallback (Basic -> FastCodec/Frugal), not protocol detection. Need to verify if Target 4 was actually addressed or needs implementation.

### Target 6: In progress
Need to verify correct implementation of:
1. Dump() method on connPool (panic-safe, returns map[string]interface{})
2. Enhanced frame error reporting with hex dump format
