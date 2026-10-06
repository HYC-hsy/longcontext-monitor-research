
# Check if the 6 required streaming types now exist
cd /app && grep -E "^type (ServerStreamingClient|ServerStreamingServer|ClientStreamingClient|ClientStreamingServer|BidiStreamingClient|BidiStreamingServer)\[" pkg/streaming/streaming.go | wc -l
