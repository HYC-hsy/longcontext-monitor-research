
# Check if Target 6 error format matches the task requirements
echo "=== Checking Target 6 error format (must have ErrFrameTooLarge and second4Bytes) ==="
grep -n "ErrFrameTooLarge.*invalid frame.*first4Bytes.*second4Bytes\|second4Bytes=%#x" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
echo "Exit code: $?"
