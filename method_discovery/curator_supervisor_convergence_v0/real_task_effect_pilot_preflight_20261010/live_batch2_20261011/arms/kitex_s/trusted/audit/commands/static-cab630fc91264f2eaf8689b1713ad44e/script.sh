
# Check transport protocol definitions
grep -n "type Protocol" /app/pkg/remote/transport.go 2>/dev/null || echo "Not found in transport.go, checking other locations"
find /app/pkg -name "*.go" -exec grep -l "TTHeaderStreaming" {} \; 2>/dev/null | head -5
