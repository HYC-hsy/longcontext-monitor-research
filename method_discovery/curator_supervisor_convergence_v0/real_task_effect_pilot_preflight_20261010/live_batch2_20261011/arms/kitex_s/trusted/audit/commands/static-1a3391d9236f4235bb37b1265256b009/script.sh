
# Check if the required internal/client types exist
grep -n "type UnaryOption\|type StreamOption\|type TTHeaderStreamingOption" /app/internal/client/option.go 2>/dev/null | head -10
echo "---"
# Check for the required option functions
grep -n "WithUnaryRPCTimeout\|WithStreamRecvTimeout\|WithUnaryMiddleware\|TailOption" /app/client/*.go 2>/dev/null
