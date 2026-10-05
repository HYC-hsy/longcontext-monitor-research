
# Check if Target 5 option files were created
ls -la /app/client/option_*.go 2>&1
echo "---"
# Check if deprecated.go was created for Target 2
ls -la /app/pkg/endpoint/deprecated.go 2>&1
echo "---"
# Check frame_debug.go that was just created
ls -la /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_debug.go 2>&1
