
# Find the transport package with Protocol constants
find /app -name "*.go" -type f -exec grep -l "type Protocol" {} \; | head -5
