
# Check streamcall.go location - should be in client/callopt/streamcall, not just callopt/streamcall
ls -la /app/callopt/streamcall.go 2>/dev/null && echo "WRONG LOCATION - should be in client/callopt/"
ls -la /app/client/callopt/streamcall.go 2>/dev/null && echo "Correct location"
