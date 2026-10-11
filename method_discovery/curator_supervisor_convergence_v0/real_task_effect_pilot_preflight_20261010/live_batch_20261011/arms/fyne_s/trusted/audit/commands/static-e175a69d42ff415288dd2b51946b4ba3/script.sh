
cd /app
# Search for Metadata() method on App interface and implementations
grep -n "Metadata()" *.go app/*.go 2>/dev/null | head -20
