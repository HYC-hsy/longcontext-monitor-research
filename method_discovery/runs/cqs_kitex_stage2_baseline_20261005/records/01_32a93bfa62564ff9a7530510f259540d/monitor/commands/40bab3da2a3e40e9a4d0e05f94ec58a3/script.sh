
# Verify Options struct now has container fields
grep -A 100 "type Options struct" /app/internal/client/option.go | grep -E "(UnaryOptions|StreamOptions|TTHeaderStreamingOptions)" | head -5
