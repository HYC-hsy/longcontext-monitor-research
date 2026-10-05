
# Check if cep and sep have the required StreamRecvEndpoint and StreamSendEndpoint with EqualsTo methods
grep -n "StreamRecvEndpoint\|StreamSendEndpoint" /app/pkg/endpoint/cep/endpoint.go /app/pkg/endpoint/sep/endpoint.go 2>/dev/null || echo "NOT FOUND"
