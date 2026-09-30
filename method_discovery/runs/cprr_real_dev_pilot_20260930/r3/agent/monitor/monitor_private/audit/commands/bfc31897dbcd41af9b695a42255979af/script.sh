
# Check callopt/streamcall for WithRecvTimeout
ls -la /app/client/callopt/streamcall/ 2>&1
cd /app && grep -n "WithRecvTimeout" client/callopt/streamcall/*.go 2>&1 | head -5
