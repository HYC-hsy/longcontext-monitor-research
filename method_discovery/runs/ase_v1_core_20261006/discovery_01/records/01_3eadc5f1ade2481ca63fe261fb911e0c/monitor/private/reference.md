Six-target streaming architecture overhaul for Go RPC framework. All targets are independent and can land separately.

**Target 1: Streaming Types**
Add type-safe streaming interfaces to pkg/streaming separating client/server roles. Header and Trailer are map[string]string aliases. ClientStream interface has SendMsg/RecvMsg/Header/Trailer/CloseSend/Context methods. ServerStream has SendMsg/RecvMsg/SetHeader/SendHeader/SetTrailer. Generic wrappers for four streaming patterns: ServerStreamingClient[Res], ServerStreamingServer[Res], ClientStreamingClient[Req,Res], ClientStreamingServer[Req,Res], BidiStreamingClient[Req,Res], BidiStreamingServer[Req,Res]. Each has factory function like NewServerStreamingClient[Res](ClientStream). ClientStreamingClient has CloseAndRecv that calls CloseSend then RecvMsg. Must extend existing Args and Result structs with ServerStream and ClientStream fields (in addition to existing Stream field). Also define CloseCallbackRegister, GRPCStreamGetter interfaces, and EventHandler type using pkg/stats.

**Target 2: Endpoint Architecture**
Create pkg/endpoint/cep (client endpoints) and pkg/endpoint/sep (server endpoints). Each has StreamEndpoint, StreamRecvEndpoint, StreamSendEndpoint with corresponding Middleware and MiddlewareBuilder types. cep.StreamEndpoint returns ClientStream; sep.StreamEndpoint takes ServerStream parameter. StreamRecvEndpoint and StreamSendEndpoint must have EqualsTo(e2) bool method in both packages. Each package has Chain functions for right-to-left composition. Note: cep needs DummyDummyMiddleware (double "Dummy"). Add UnaryEndpoint, UnaryMiddleware, UnaryMiddlewareBuilder, UnaryChain to pkg/endpoint with bidirectional conversion methods. Deprecated types (RecvEndpoint, SendEndpoint, etc.) go in pkg/endpoint/deprecated.go using old streaming.Stream interface.

**Target 3: Transport Protocol Reorganization**
Critical: TTHeaderStreaming must become dedicated power-of-2 flag with value 64 (not composite). Add GRPCStreaming as value 128. Existing values must not change: PurePayload=0, TTHeader=2, Framed=4, HTTP=8, GRPC=16, HESSIAN2=32. TTHeaderFramed remains composite (TTHeader|Framed). String() method must return flag name for individual flags, pipe-separated ascending-order composition for multiple flags (e.g., "TTHeader|Framed"), "PurePayload" for zero. Exception: HESSIAN2.String() returns "Hessian2". Change default transport protocol from PurePayload to Framed.

**Target 4: Thrift Codec Fallback**
MarshalThriftData and UnmarshalThriftData in pkg/remote/codec/thrift must succeed with Basic codec when message types support alternative serialization (FastCodec or Frugal). Fallback behavior must be consistent regardless of codec type.

**Target 5: Client Option Categories**
Separate client options into three namespaces: UnaryOption, StreamOption, TTHeaderStreamingOption. Type aliases reference internal/client types. Create option_unary.go with WithUnaryOptions, WithUnaryRPCTimeout, WithUnaryMiddleware, WithUnaryMiddlewareBuilder. Create option_stream.go with WithStreamOptions, WithStreamRecvTimeout (sets RecvTimeout on StreamOptions), WithStreamMiddleware variants using cep types. Create option_ttstream.go with WithTTHeaderStreamingOptions, WithTTHeaderStreamingTransportOptions. Add TailOption wrapper that stores options for deferred execution. Add WithRecvTimeout to client/callopt/streamcall. Critical: migrate retry/fallback options (WithFailureRetry, WithBackupRequest, WithRetryContainer, WithFallback, WithSpecifiedResultRetry) to store in UnaryOptions fields (RetryMethodPolicies, RetryContainer, Fallback, RetryWithResult) not old locations.

**Target 6: gRPC Diagnostics**
Add Dump() interface{} method to connPool in pkg/remote/trans/nphttp2/conn_pool.go returning map[string]interface{} with panic recovery. Replace standalone readFrameHeader in pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go with (fr *Framer) readAndCheckFrameHeader() method. When frame size exceeds maxReadSize, error must include both http2.ErrFrameTooLarge text and "invalid frame" with hex-formatted first4Bytes and second4Bytes.

**Integration Constraints**
Backward compatibility required - existing Stream interface, Endpoint types, Protocol constants remain usable. The new Header/Trailer types are separate from existing metadata.MD usage. Args/Result extension is additive. Default transport change affects new clients unless explicitly configured otherwise.

**Distinguishing Evidence**
Protocol.String() output change is observable: TTHeaderStreaming should return "TTHeaderStreaming" not "TTHeader|STREAMING". Composite values show pipe separation. Client option migration moves retry fields to UnaryOptions substructure. StreamRecvEndpoint/StreamSendEndpoint must support EqualsTo comparison. Generic factory functions must handle type parameters correctly. CloseAndRecv behavior differs from separate calls (error from CloseSend prevents RecvMsg).
