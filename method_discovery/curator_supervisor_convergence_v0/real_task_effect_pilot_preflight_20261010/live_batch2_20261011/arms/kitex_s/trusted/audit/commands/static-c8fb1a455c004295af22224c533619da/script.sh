
# Check what middleware types were actually created in cep package
grep -n "type.*Middleware" /app/pkg/endpoint/cep/*.go | head -15
echo "---"
# Check the exact type names required per task
echo "Required per task: StreamMiddleware, StreamRecvMiddleware, StreamSendMiddleware"
