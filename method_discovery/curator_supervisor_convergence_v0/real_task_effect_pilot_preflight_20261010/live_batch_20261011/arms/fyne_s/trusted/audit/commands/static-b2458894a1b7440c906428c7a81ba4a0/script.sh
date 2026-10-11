
# Check Target 6: validation.NewAllStrings signature
if [ -f /app/data/validation/all.go ]; then
    echo "=== data/validation/all.go exists ==="
    grep -B 5 -A 15 "func NewAllStrings" /app/data/validation/all.go
else
    echo "ERROR: data/validation/all.go does NOT exist"
fi
