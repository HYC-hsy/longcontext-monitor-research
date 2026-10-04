
# Check what's in the original files and the deprecated.go
cd /app
echo "=== recv_endpoint.go ==="
head -40 pkg/endpoint/recv_endpoint.go
echo ""
echo "=== send_endpoint.go ==="
head -40 pkg/endpoint/send_endpoint.go
echo ""
echo "=== deprecated.go (first 30 lines) ==="
head -30 pkg/endpoint/deprecated.go
