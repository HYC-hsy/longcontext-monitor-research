
# Check if all factory functions exist
cd /app && echo "Factory functions:"
grep -c "^func NewServerStreamingClient" pkg/streaming/streaming.go
grep -c "^func NewServerStreamingServer" pkg/streaming/streaming.go
grep -c "^func NewClientStreamingClient" pkg/streaming/streaming.go
grep -c "^func NewClientStreamingServer" pkg/streaming/streaming.go
grep -c "^func NewBidiStreamingClient" pkg/streaming/streaming.go
grep -c "^func NewBidiStreamingServer" pkg/streaming/streaming.go
