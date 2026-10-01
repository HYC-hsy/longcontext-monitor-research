
# Search for Protocol type definition with TTHeaderStreaming
grep -r "TTHeaderStreaming.*=" /app --include="*.go" | grep -v "test" | head -5
