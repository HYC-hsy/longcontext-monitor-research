
# Check if UnaryOptions, StreamOptions, TTHeaderStreamingOptions types exist
grep -r "type UnaryOptions" /app/internal/client/ /app/client/ 2>/dev/null
grep -r "type StreamOptions" /app/internal/client/ /app/client/ 2>/dev/null
grep -r "type TTHeaderStreamingOptions" /app/internal/client/ /app/client/ 2>/dev/null
