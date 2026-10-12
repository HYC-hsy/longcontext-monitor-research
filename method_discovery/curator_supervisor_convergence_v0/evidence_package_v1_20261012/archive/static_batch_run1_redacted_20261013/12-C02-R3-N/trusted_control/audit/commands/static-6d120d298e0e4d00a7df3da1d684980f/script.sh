
# Check if there's handling for Bytes and URI in sprintf Set
cd /app && grep -A 30 "case Bytes:" data/binding/sprintf.go
