This is a Go RPC framework enhancement requiring 6 independent architectural improvements. All targets must maintain backward compatibility with existing APIs.

**Target 1: Streaming Types and Generic Interfaces**

Introduces type-safe streaming abstractions separating client/server roles. Header and Trailer are map[string]string (distinct from existing metadata.MD). ClientStream provides SendMsg/RecvMsg/Header/Trailer/CloseSend/Context methods. ServerStream provides SendMsg/RecvMsg/SetHeader/SendHeader/SetTrailer methods (note SetHeader vs SendHeader ordering difference). Eight generic wrapper types (ServerStreamingClient[Res], ServerStreamingServer[Res], ClientStreamingClient[Req,Res], ClientStreamingServer[Req,Res], BidiStreamingClient[Req,Res], BidiStreamingServer[Req,Res]) with factory functions that delegate to base streams. Args and Result structs extended with both ServerStream and ClientStream fields alongside existing Stream field for compatibility. CloseCallbackRegister, GRPCStreamGetter, and EventHandler (func(ctx, stats.Event, error)) interfaces required.

Critical distinction: Generic Recv methods allocate new instances and call RecvMsg; Send methods pass pointer directly to SendMsg. ClientStreamingClient.CloseAndRecv must call CloseSend first, return (nil, err) if CloseSend fails.

**Target 2: Endpoint Architecture Reorganization**

Creates pkg/endpoint/cep (client endpoints) and pkg/endpoint/sep (server endpoints) packages. Client-side: cep.StreamEndpoint returns ClientStream, has recv/send endpoint types and middleware builders. Server-side: sep.StreamEndpoint takes ServerStream parameter, has recv/send endpoint types and middleware builders. Both cep.StreamRecvEndpoint and cep.StreamSendEndpoint require EqualsTo(e2) bool method returning true only if same underlying function. Same EqualsTo requirement for sep versions.

Base endpoint package gains UnaryEndpoint (type alias of Endpoint), UnaryMiddleware with ToMiddleware/ToUnaryMiddleware conversion methods, UnaryChain. Deprecated types (RecvEndpoint, SendEndpoint, their middleware/builder/chain functions) go in pkg/endpoint/deprecated.go referencing old streaming.Stream interface. All Chain functions compose right-to-left.

Special requirement: cep.DummyDummyMiddleware (double "Dummy" is intentional) returns next unchanged.

**Target 3: Transport Protocol Reorganization**

Protocol constant restructuring: TTHeaderStreaming becomes dedicated power-of-2 flag with value 64 (not composite TTHeader|STREAMING). New GRPCStreaming flag value 128. Existing values unchanged: PurePayload=0, TTHeader=2, Framed=4, HTTP=8, GRPC=16, HESSIAN2=32. TTHeaderFramed remains composite (TTHeader | Framed).

String() method critical distinction: Single flags return flag name (TTHeaderStreaming.String() → "TTHeaderStreaming", exception: HESSIAN2 → "Hessian2"). Composite values return pipe-separated names in ascending bit order (TTHeaderFramed.String() → "TTHeader|Framed", (GRPC|Framed).String() → "Framed|GRPC" since 4<16). Zero value returns "PurePayload".

Default transport protocol changes from PurePayload to Framed affecting all new RPC configurations.

**Target 4: Thrift Codec Fallback Enhancement**

Current marshalThriftData and unmarshalThriftData have fallback logic guarded by "if c.CodecType != Basic" (lines 62-69, 118-124 in thrift_data.go). This prevents Basic codec from using FastCodec/Frugal alternatives even when available. Requirement: Remove Basic codec exclusion so fallback attempts FastCodec then Frugal regardless of codec type. Fallback consistency means primary codec failure always attempts alternatives when message type supports them.

**Target 5: Client Option Category System**

Type aliases in client/option.go: UnaryOption, UnaryOptions, StreamOption, StreamOptions, TTHeaderStreamingOption, TTHeaderStreamingOptions (all alias internal/client types). Three new option files: option_unary.go (WithUnaryOptions, WithUnaryRPCTimeout, WithUnaryMiddleware, WithUnaryMiddlewareBuilder), option_stream.go (WithStreamOptions, WithStreamRecvTimeout setting o.RecvTimeout on StreamOptions, stream middleware functions using cep types), option_ttstream.go (WithTTHeaderStreamingOptions, WithTTHeaderStreamingTransportOptions).

TailOption(opt) wraps option for storage in o.TailOptions and deferred execution. WithRecvTimeout in client/callopt/streamcall sets o.StreamOptions.RecvTimeout. Existing retry/fallback options (WithFailureRetry, WithBackupRequest, WithRetryContainer, WithFallback, WithSpecifiedResultRetry) must migrate storage from old o.RetryMethodPolicies to o.UnaryOptions.RetryMethodPolicies and related UnaryOptions fields.

**Target 6: gRPC Diagnostics Enhancement**

conn_pool.go requires Dump() interface{} method returning map[string]interface{} where keys are remote addresses and values are slices of transport dumps. Must be panic-safe with recovery and error logging. Return value must be JSON-serializable.

frame_reader.go: Replace standalone readFrameHeader(r) function with Framer method readAndCheckFrameHeader() (http2.FrameHeader, error). When frame size exceeds maxReadSize, return error containing both http2.ErrFrameTooLarge text and "invalid frame" with hex-formatted bytes: fmt.Errorf("%s or invalid frame (first4Bytes=%#x, second4Bytes=%#x)", http2.ErrFrameTooLarge, buf[:4], buf[4:8]).

**Integration Consequences**

Old streaming.Stream interface remains alongside new ClientStream/ServerStream. Args/Result have three stream fields: Stream (old), ClientStream, ServerStream. Protocol String() output change may affect logging/monitoring expecting old format. Default protocol change from PurePayload to Framed affects performance characteristics and requires codec support. Option categorization prevents accidental application of stream options to unary calls and vice versa.

**False Positive Risks**

Test passing with wrong String() output for composites (must show pipes). Factory function appearing to work but not actually delegating to base stream methods. EqualsTo method returning true for different functions. Fallback appearing to work for Basic codec due to test only using FastCodec-enabled types. TailOption executing in wrong order. Dump panic crashing instead of recovering.
