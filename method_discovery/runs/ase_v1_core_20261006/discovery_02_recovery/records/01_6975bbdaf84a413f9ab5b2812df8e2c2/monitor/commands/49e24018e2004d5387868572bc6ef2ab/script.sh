
# Check what factory functions exist
cd /app && grep -E "^func New(ServerStreaming|ClientStreaming|BidiStreaming)" pkg/streaming/streaming.go || echo "NONE OF THE REQUIRED FACTORIES FOUND"
