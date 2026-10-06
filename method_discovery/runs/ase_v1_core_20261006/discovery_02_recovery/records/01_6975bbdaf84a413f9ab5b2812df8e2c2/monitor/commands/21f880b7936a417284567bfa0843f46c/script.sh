
# Check what has been implemented for Target 6
cd /app && grep -n "Dump()" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -5
cd /app && grep -n "invalid frame" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -5
