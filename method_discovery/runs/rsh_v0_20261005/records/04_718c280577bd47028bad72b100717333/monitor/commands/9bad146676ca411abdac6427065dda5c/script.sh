
# Search for Protocol type definition
find /app -name "*.go" -type f | xargs grep -l "type Protocol" | head -5
