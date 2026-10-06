
# Check what streaming types are actually defined
cd /app && grep -E "^type (ServerStreamingClient|ServerStreamingServer|ClientStreamingClient|ClientStreamingServer|BidiStreamingClient|BidiStreamingServer)" pkg/streaming/streaming.go || echo "NONE OF THE REQUIRED TYPES FOUND"
