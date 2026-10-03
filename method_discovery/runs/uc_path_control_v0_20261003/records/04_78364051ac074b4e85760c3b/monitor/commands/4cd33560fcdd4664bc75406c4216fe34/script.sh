
# Check if Target 6 methods exist
grep -n "func.*Dump()" /app/pkg/remote/trans/nphttp2/conn_pool.go
grep -n "readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
