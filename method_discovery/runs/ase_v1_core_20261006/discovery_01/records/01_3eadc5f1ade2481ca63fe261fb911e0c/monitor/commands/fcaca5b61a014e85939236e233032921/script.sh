
# Check for transport package location and Protocol type
find /app -name "*.go" -type f | xargs grep -l "type Protocol" | head -5
