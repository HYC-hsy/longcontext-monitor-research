
# Check if any of the new packages/files have been created
ls -la /app/pkg/endpoint/cep 2>&1
echo "---"
ls -la /app/pkg/endpoint/sep 2>&1
echo "---"
ls -la /app/pkg/endpoint/deprecated.go 2>&1
echo "---"
# Check if streaming has new type definitions beyond the current Stream
grep -n "type ClientStream\|type ServerStream\|type Header\|type Trailer" /app/pkg/streaming/*.go 2>&1
echo "---"
# Check for new client option files
ls /app/client/option_unary.go /app/client/option_stream.go /app/client/option_ttstream.go 2>&1
