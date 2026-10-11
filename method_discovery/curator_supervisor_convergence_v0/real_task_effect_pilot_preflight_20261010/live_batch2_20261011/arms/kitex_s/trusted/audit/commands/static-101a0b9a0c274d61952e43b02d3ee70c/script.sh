
# Find transport protocol definitions
find /app/pkg/remote -name "*.go" -exec grep -l "type Protocol" {} \; 2>/dev/null | head -3
