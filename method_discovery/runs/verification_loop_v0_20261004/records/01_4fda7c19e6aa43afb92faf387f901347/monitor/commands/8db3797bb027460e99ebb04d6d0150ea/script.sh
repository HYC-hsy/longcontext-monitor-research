
# Check for mobile or driver-specific app implementations
cd /app
find . -path "*/mobile/*" -name "*.go" -o -path "*/driver/*" -name "app*.go" | head -20
