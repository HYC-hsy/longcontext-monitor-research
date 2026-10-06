Go RPC framework streaming architecture overhaul with 6 independent targets:

**Target 1: Streaming Types and Generic Interfaces** (pkg/streaming)
- New types: Header, Trailer (map[string]string aliases)
- Base interfaces: ClientStream (6 methods including SendMsg/RecvMsg/Header/Trailer/CloseSend/Context), ServerStream (5 methods including SendMsg/RecvMsg/SetHeader/SendHeader/SetTrailer)
- Generic wrappers for 4 patterns: ServerStreamingClient[Res], ServerStreamingServer[Res], ClientStreamingClient[Req,Res], ClientStreamingServer[Req,Res], BidiStreamingClient[Req,Res], BidiStreamingServer[Req,Res]
- Each wrapper has factory function (NewXxx) that delegates to underlying base stream
- Extensions: Args and Result structs gain ServerStream/ClientStream fields (old Stream field remains)
- Additional interfaces: CloseCallbackRegister, GRPCStreamGetter, EventHandler type (func(context.Context, stats.Event, error))
- Type safety via generics: Recv/Send methods use *Req/*Res not interface{}

**Target 2: Endpoint Architecture Reorganization**
- New packages: pkg/endpoint/cep (client endpoints), pkg/endpoint/sep (server endpoints)
- cep: StreamEndpoint returns ClientStream, has StreamRecvEndpoint/StreamSendEndpoint with EqualsTo methods, chain functions, DummyDummyMiddleware (note double Dummy)
- sep: StreamEndpoint takes ServerStream parameter (not return), same pattern for Recv/Send endpoints
- pkg/endpoint additions: UnaryEndpoint (type alias of Endpoint), UnaryMiddleware, conversion methods ToMiddleware/ToUnaryMiddleware
- Deprecated in pkg/endpoint: RecvEndpoint/SendEndpoint operating on old streaming.Stream interface (deprecated.go file)
- Right-to-left composition for all Chain functions

**Target 3: Transport Protocol Reorganization** (transport package)
- TTHeaderStreaming becomes dedicated flag (value 64, not composite)
- New flag: GRPCStreaming (value 128)
- Existing values unchanged: PurePayload=0, TTHeader=2, Framed=4, HTTP=8, GRPC=16, HESSIAN2=32
- TTHeaderFramed remains composite (TTHeader | Framed)
- String() method: individual flags return name (except HESSIAN2→"Hessian2"), composites return pipe-separated ascending bit order, zero returns "PurePayload"
- Default protocol changes from PurePayload to Framed

**Target 4: Thrift Codec Fallback Enhancement** (pkg/remote/codec/thrift)
- MarshalThriftData and UnmarshalThriftData must succeed with Basic codec when FastCodec or Frugal available
- Consistency: codec type should not prevent fallback to available alternatives

**Target 5: Client Option Category System** (client package)
- Three namespaces: UnaryOption, StreamOption, TTHeaderStreamingOption with corresponding Options containers
- New files: client/option_unary.go, client/option_stream.go, client/option_ttstream.go
- Type aliases in client/option.go for internal/client types
- Unary: WithUnaryOptions, WithUnaryRPCTimeout, WithUnaryMiddleware, WithUnaryMiddlewareBuilder
- Stream: WithStreamOptions, WithStreamRecvTimeout (sets RecvTimeout on StreamOptions), middleware functions using cep types
- TTHeaderStreaming: WithTTHeaderStreamingOptions, WithTTHeaderStreamingTransportOptions
- TailOption wrapper for options needing late execution
- client/callopt/streamcall: WithRecvTimeout sets StreamOptions.RecvTimeout
- Retry field migration: existing retry options store in o.UnaryOptions.* fields not top-level o.* fields

**Target 6: gRPC Diagnostics Enhancement**
- pkg/remote/trans/nphttp2/conn_pool.go: Dump() method returns map[string]interface{} (addresses to transport dump slices), panic-safe, JSON-serializable
- pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go: replace readFrameHeader function with (fr *Framer) readAndCheckFrameHeader() method, enhance error with hex dump of first 8 bytes when invalid frame detected

**Critical constraints:**
- Backward compatibility required for existing APIs
- Old streaming.Stream interface remains but deprecated
- EqualsTo methods required specifically on StreamRecvEndpoint and StreamSendEndpoint in both cep and sep
- DummyDummyMiddleware has intentional double "Dummy" naming
- Protocol String() output format matters for tooling/debugging (exact format specified)
- Middleware composition order is right-to-left for all Chain functions

**Integration consequences:**
- Generic types require Go 1.18+ (project already uses generics based on go.mod)
- New endpoint packages allow separate middleware chains for client vs server streams
- Protocol reorganization affects transport selection logic throughout codebase
- Option categorization prevents accidental cross-application (unary options shouldn't affect streaming)

**False positive risks:**
- Tests may pass if String() implementation incomplete (need to test composite values and ordering)
- Generic factory functions could appear correct without proper delegation
- EqualsTo method might be missing or incorrectly implemented
- Fallback logic might work for some codec types but not Basic specifically
- Retry options might go to wrong fields (old vs new UnaryOptions)

**State distinctions:**
- Protocol constants: check actual numeric values not just String() output
- Generic wrappers: verify factory creates working implementation not just interface satisfaction
- Endpoint packages: cep StreamEndpoint returns stream, sep StreamEndpoint takes stream parameter
- Option storage: UnaryOptions field presence vs top-level fields for retry/fallback
- Codec fallback: Basic codec specifically must use fallback path
