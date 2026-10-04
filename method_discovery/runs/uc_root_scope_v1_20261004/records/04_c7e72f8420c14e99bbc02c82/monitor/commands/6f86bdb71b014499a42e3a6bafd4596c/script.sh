
# Check Target 5: Are the required option functions actually implemented?
echo "=== Checking Target 5 required functions ==="

# Check for WithUnaryOptions in client package
grep -r "func WithUnaryOptions" /app/client/ 2>/dev/null | head -5

# Check for WithStreamOptions
grep -r "func WithStreamOptions" /app/client/ 2>/dev/null | head -5

# Check for TailOption
grep -r "func TailOption" /app/client/ 2>/dev/null | head -5

# Check for WithRecvTimeout in callopt/streamcall
find /app/client -name "streamcall*" -o -path "*/callopt/*" 2>/dev/null | grep -v ".go:" | head -10
