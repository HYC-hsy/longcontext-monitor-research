
# Check what was actually created for streaming types
cd /app && grep -E "^type (ServerStreamingClient|ClientStreamingClient|BidiStreamingClient|ServerStreamingServer|ClientStreamingServer|BidiStreamingServer)" pkg/streaming/streaming.go
