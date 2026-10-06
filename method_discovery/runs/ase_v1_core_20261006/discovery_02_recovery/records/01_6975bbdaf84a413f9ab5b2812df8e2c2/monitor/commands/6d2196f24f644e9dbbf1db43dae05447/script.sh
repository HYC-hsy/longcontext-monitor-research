
# Check if StreamEndpoint returns ClientStream (correct signature)
cd /app && grep "type StreamEndpoint" pkg/endpoint/cep/endpoint.go

# Check for StreamRecvEndpoint, StreamSendEndpoint
cd /app && grep -E "type Stream(Recv|Send)Endpoint" pkg/endpoint/cep/endpoint.go

# Check for EqualsTo method
cd /app && grep -c "EqualsTo" pkg/endpoint/cep/endpoint.go
