Streaming architecture overhaul for Go RPC framework with 6 targets. Framework must support both gRPC and TTHeader streaming through unified abstraction.

**Target 1: Streaming Types (pkg/streaming)**
- ClientStream and ServerStream base interfaces with distinct method sets (client has Header/Trailer getters and CloseSend; server has SetHeader/SendHeader/SetTrailer)
- Generic wrappers for 4 streaming patterns: ServerStreamingClient/Server[Res], ClientStreamingClient/Server[Req,Res], BidiStreamingClient/Server[Req,Res]
- Factory functions allocate new message instances and delegate to base stream SendMsg/RecvMsg
- ClientStreamingClient.CloseAndRecv must call CloseSend before RecvMsg; return (nil, err) if CloseSend fails
- Args/Result structs extended with ServerStream and ClientStream fields (in addition to existing Stream field)
- Additional interfaces: CloseCallbackRegister, GRPCStreamGetter, EventHandler type alias

**Target 2: Endpoint Architecture**
- New packages: pkg/endpoint/cep (client endpoints) and pkg/endpoint/sep (server endpoints)
- cep.StreamEndpoint returns ClientStream; sep.StreamEndpoint takes ServerStream parameter (asymmetric signatures)
- StreamRecvEndpoint and StreamSendEndpoint must have EqualsTo(e2) bool method (reference equality check)
- All Chain functions compose right-to-left (same as existing endpoint.Chain)
- cep has DummyDummyMiddleware (double "Dummy" intentional)
- pkg/endpoint gets UnaryEndpoint type with bidirectional conversions to/from Middleware
- Old RecvEndpoint/SendEndpoint moved to deprecated.go, use old streaming.Stream interface

**Target 3: Transport Protocol (transport package)**
- TTHeaderStreaming = 64 (dedicated flag, not composite)
- GRPCStreaming = 128 (new dedicated flag)
- Existing values unchanged: PurePayload=0, TTHeader=2, Framed=4, HTTP=8, GRPC=16, HESSIAN2=32
- String() output: single flags return name (except HESSIAN2→"Hessian2"), composites return pipe-separated in ascending bit order
- TTHeaderStreaming.String() = "TTHeaderStreaming" (single name, not composition)
- TTHeaderFramed.String() = "TTHeader|Framed" (composite, TTHeader=2 < Framed=4)
- Default protocol changes from PurePayload to Framed

**Target 4: Thrift Codec Fallback**
- MarshalThriftData and UnmarshalThriftData must succeed with Basic codec when message supports FastCodec or Frugal
- Fallback logic must be consistent regardless of codec type
- Existing code shows fallback only when c.CodecType != Basic; must extend to include Basic

**Target 5: Client Options**
- Three option namespaces: UnaryOption, StreamOption, TTHeaderStreamingOption (from internal/client)
- New files: client/option_unary.go, client/option_stream.go, client/option_ttstream.go
- Retry/fallback fields migrate to UnaryOptions: RetryMethodPolicies, RetryContainer, Fallback, RetryWithResult
- StreamOption.WithStreamRecvTimeout stores in StreamOptions.RecvTimeout
- TailOption wrapper defers execution to after other options
- callopt/streamcall package gets WithRecvTimeout for call-level stream timeout

**Target 6: gRPC Diagnostics**
- connPool.Dump() returns map[string]interface{} (address→slice of transport dumps), must be panic-safe and JSON-serializable
- Framer.readAndCheckFrameHeader() replaces standalone readFrameHeader function
- Frame size error includes hex dump: "...ErrFrameTooLarge text... or invalid frame (first4Bytes=0x..., second4Bytes=0x...)"

**Integration concerns:**
- Generic type parameters require Go 1.18+
- EqualsTo method on function types needs runtime function pointer comparison (may require reflection or wrapper struct)
- Existing streaming.Stream interface preserved for backward compatibility (now deprecated)
- middleware chain order affects execution; right-to-left composition must be consistent across all Chain functions
- Option categorization changes where retry policies are stored; must update all existing option implementations to use o.UnaryOptions fields

**False positive risks:**
- Test passing with wrong String() output (e.g., "TTHeader|STREAMING" instead of "TTHeaderStreaming")
- Factory functions that don't allocate new instances (reusing pointer would break concurrent recv)
- CloseAndRecv not checking CloseSend error
- Chain composing left-to-right instead of right-to-left
- Fallback still skipping Basic codec type
- Options storing in old o.RetryMethodPolicies instead of o.UnaryOptions.RetryMethodPolicies
