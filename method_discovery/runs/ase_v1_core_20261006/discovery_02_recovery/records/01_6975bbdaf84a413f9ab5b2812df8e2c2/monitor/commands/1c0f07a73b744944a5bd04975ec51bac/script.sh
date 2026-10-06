
# Check if the 6 required streaming types now exist
cd /app && echo "Checking for required streaming types:"
grep -c "^type ServerStreamingClient\[" pkg/streaming/streaming.go || echo "ServerStreamingClient: 0"
grep -c "^type ServerStreamingServer\[" pkg/streaming/streaming.go || echo "ServerStreamingServer: 0"
grep -c "^type ClientStreamingClient\[" pkg/streaming/streaming.go || echo "ClientStreamingClient: 0"
grep -c "^type ClientStreamingServer\[" pkg/streaming/streaming.go || echo "ClientStreamingServer: 0"
grep -c "^type BidiStreamingClient\[" pkg/streaming/streaming.go || echo "BidiStreamingClient: 0"
grep -c "^type BidiStreamingServer\[" pkg/streaming/streaming.go || echo "BidiStreamingServer: 0"
