
# Check if TailOption was added
grep -n "func TailOption" /app/client/option.go 2>/dev/null || echo "TailOption NOT FOUND"
echo "---"
# Check what's in streamcall.go
head -50 /app/callopt/streamcall.go 2>/dev/null || head -50 /app/client/callopt/streamcall.go 2>/dev/null
