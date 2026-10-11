
# Check if streamcall subdirectory exists with WithRecvTimeout
find /app/client/callopt -name "*stream*" -type f 2>/dev/null
echo "---"
# Check if TailOption was added to option.go
grep -n "TailOption" /app/client/option.go | head -5
