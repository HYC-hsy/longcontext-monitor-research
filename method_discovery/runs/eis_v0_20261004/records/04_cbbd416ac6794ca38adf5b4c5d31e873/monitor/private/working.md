# Monitor Working Note - RPC Framework Streaming Architecture Overhaul

## Task Understanding

Six interconnected targets for overhauling streaming architecture in a Go RPC framework:

### Target 1: Streaming Types and Generic Interfaces
**Core requirement**: New type-safe, protocol-agnostic streaming interfaces in `pkg/streaming`

Key elements to verify:
- `Header` and `Trailer` type aliases (map[string]string)
- `ClientStream` interface with 6 methods (SendMsg, RecvMsg, Header, Trailer, CloseSend, Context)
- `ServerStream` interface with 5 methods (SendMsg, RecvMsg, SetHeader, SendHeader, SetTrailer)
- 8 generic typed wrapper interfaces with factory functions:
  - ServerStreamingClient[Res], ServerStreamingServer[Res]
  - ClientStreamingClient[Req, Res], ClientStreamingServer[Req, Res]
  - BidiStreamingClient[Req, Res], BidiStreamingServer[Req, Res]
- Extension of existing `Args` and `Result` structs with ServerStream/ClientStream fields
- `CloseCallbackRegister`, `GRPCStreamGetter`, `EventHandler` types

**Baseline**: Current `streaming.go` has old `Stream` interface and basic Args/Result structs

### Target 2: Endpoint Architecture Reorganization
**Core requirement**: New packages `pkg/endpoint/cep` (client endpoints) and `pkg/endpoint/sep` (server endpoints)

Key elements:
- `pkg/endpoint/cep`: StreamEndpoint (returns ClientStream), StreamRecvEndpoint/StreamSendEndpoint (with EqualsTo methods), middleware types, Chain functions, DummyDummyMiddleware (note: double "Dummy")
- `pkg/endpoint/sep`: StreamEndpoint (takes ServerStream param), StreamRecvEndpoint/StreamSendEndpoint, middleware types, Chain functions
- `pkg/endpoint`: UnaryEndpoint, UnaryMiddleware types with conversion methods (ToMiddleware/ToUnaryMiddleware)
- Deprecated types in `pkg/endpoint/deprecated.go` referencing old streaming.Stream

**Baseline**: `/app/pkg/endpoint/cep` and `/app/pkg/endpoint/sep` do not exist yet

### Target 3: Transport Protocol Reorganization
**Core requirement**: Restructure protocol constants in `transport` package

Key changes:
- TTHeaderStreaming must be dedicated power-of-2 flag (value 64), not composite
- Add GRPCStreaming as dedicated flag (value 128)
- String() method must produce flag name for single flags, pipe-separated composition for composite (e.g., "TTHeader|Framed")
- Change default transport protocol from PurePayload to Framed

**Baseline**: Current `transport/keys.go` has TTHeaderStreaming = TTHeader | STREAMING (composite)

### Target 4: Thrift Codec Fallback Enhancement
**Core requirement**: Basic codec must fall back to FastCodec/Frugal when available

Key elements:
- MarshalThriftData must succeed with Basic codec when alternative serialization available
- UnmarshalThriftData must succeed with Basic codec when alternative serialization available
- Fallback behavior must be consistent regardless of codec type

**Location**: `pkg/remote/codec/thrift`

### Target 5: Client Option Category System
**Core requirement**: Separate client options into unary/streaming/TTHeader-streaming namespaces

Key elements:
- New option type aliases in `client/option.go`
- New files: `client/option_unary.go`, `client/option_stream.go`, `client/option_ttstream.go`
- TailOption mechanism for delayed option execution
- WithRecvTimeout in `client/callopt/streamcall`
- Retry/fallback field migration to UnaryOptions

**Baseline**: Client package exists, need to check current option structure

### Target 6: gRPC Diagnostics Enhancement
**Core requirement**: Connection pool dump and enhanced frame error messages

Key elements:
- Dump() method on connPool in `pkg/remote/trans/nphttp2/conn_pool.go`
- Replace standalone readFrameHeader with (fr *Framer) readAndCheckFrameHeader() method
- Enhanced error message with hex dump of frame header bytes

**Location**: `pkg/remote/trans/nphttp2`

## Current Status - Turn 30

**Targets 1-4: COMPLETED and VERIFIED**
- Target 1: streaming.go compiles with all new types ✓
- Target 2: pkg/endpoint/cep and pkg/endpoint/sep created and compile ✓
- Target 3: transport/keys.go fixed with correct protocol constants and String() method ✓
- Target 4: Thrift codec fallback implemented ✓

**Target 5: IN PROGRESS**
Agent is reading client/option.go to categorize options into unary/streaming/TTHeader-streaming namespaces.

**Target 6: NOT STARTED**

## Interventions Made

1. Turn 11: Fixed streaming.go duplicate package declaration issue
2. Turn 23: Fixed transport protocol constants (Framed=4, TTHeader=2)
3. Turn 27: Fixed transport/keys.go (strings import, TTHeaderFramed, HESSIAN2 casing)

## Remaining Verification Needed

Target 5 requirements:
- Option type aliases in client/option.go
- New files: option_unary.go, option_stream.go, option_ttstream.go
- TailOption mechanism
- WithRecvTimeout in client/callopt/streamcall
- Retry/fallback field migration

Target 6 requirements:
- Dump() method on connPool
- readAndCheckFrameHeader() method replacing readFrameHeader
- Enhanced frame error messages with hex dump
