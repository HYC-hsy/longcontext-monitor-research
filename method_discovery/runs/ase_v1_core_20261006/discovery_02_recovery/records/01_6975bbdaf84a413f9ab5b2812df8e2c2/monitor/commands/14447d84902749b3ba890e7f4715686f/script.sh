
# Check if the required streaming types were added after intervention
cd /app && grep -E "^type (ServerStreamingClient|ServerStreamingServer|ClientStreamingClient|ClientStreamingServer|BidiStreamingClient|BidiStreamingServer)" pkg/streaming/streaming.go
