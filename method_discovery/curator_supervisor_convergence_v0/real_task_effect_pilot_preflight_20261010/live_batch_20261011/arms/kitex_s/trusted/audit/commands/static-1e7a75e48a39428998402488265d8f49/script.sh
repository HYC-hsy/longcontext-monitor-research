
# Check if WithRecvTimeout exists in streamcall
echo "=== Checking for WithRecvTimeout in streamcall ==="
if [ -d /app/client/callopt/streamcall ]; then
    grep -n "WithRecvTimeout" /app/client/callopt/streamcall/*.go || echo "WithRecvTimeout not found"
else
    echo "streamcall directory does not exist"
fi
