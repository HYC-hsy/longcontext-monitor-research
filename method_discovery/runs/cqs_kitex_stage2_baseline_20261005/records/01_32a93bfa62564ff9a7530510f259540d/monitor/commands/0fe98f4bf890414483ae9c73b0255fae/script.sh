
# Check if Options struct has UnaryOptions, StreamOptions, TTHeaderStreamingOptions fields
grep -A 80 "type Options struct" /app/internal/client/option.go | grep -E "(UnaryOptions|StreamOptions|TTHeaderStreamingOptions|RetryMethodPolicies)"
