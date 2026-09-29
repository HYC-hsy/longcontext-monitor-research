
# Verify the three required files were created
ls -la /app/client/option_unary.go /app/client/option_stream.go /app/client/option_ttstream.go 2>&1
echo "---"
# Check if WithRecvTimeout was added
grep -l "WithRecvTimeout" /app/client/callopt/streamcall/*.go 2>&1 || echo "WithRecvTimeout not found"
