
# Check EqualsTo fixes in cep package
grep -A 2 "func (e StreamRecvEndpoint) EqualsTo" /app/pkg/endpoint/cep/endpoint.go
grep -A 2 "func (e StreamSendEndpoint) EqualsTo" /app/pkg/endpoint/cep/endpoint.go

# Check if reflect import was added
grep "\"reflect\"" /app/pkg/endpoint/cep/endpoint.go
