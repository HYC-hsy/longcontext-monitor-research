
# Verify the 6 required streaming types still exist after the patch
cd /app && echo "Checking 6 required types:"
grep -c "^type ServerStreamingClient\[" pkg/streaming/streaming.go
grep -c "^type ServerStreamingServer\[" pkg/streaming/streaming.go  
grep -c "^type ClientStreamingClient\[" pkg/streaming/streaming.go
grep -c "^type ClientStreamingServer\[" pkg/streaming/streaming.go
grep -c "^type BidiStreamingClient\[" pkg/streaming/streaming.go
grep -c "^type BidiStreamingServer\[" pkg/streaming/streaming.go
