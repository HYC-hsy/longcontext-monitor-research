
# Check if Bytes, Rune, and URI types are handled in Get() method
cd /app && grep -B 5 -A 10 "case Bytes:\|case Rune:\|case URI:" data/binding/sprintf.go | head -40
