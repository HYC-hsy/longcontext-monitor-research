
# Check if NewSprintf registers DataChanged listeners on sources
echo "=== NewSprintf listener registration ===" 
grep -A 30 "^func NewSprintf" /app/data/binding/sprintf.go | grep -E "AddListener|DataChanged|listener"

echo ""
echo "=== Verify reactive binding behavior ==="
grep -n "AddListener\|DataListener\|listener" /app/data/binding/sprintf.go
