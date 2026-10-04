
# Check if the required Target 5 functions exist
echo "=== Checking for required Target 5 functions ==="

echo -e "\n1. TailOption in client/option.go:"
grep -n "func TailOption" /app/client/option.go

echo -e "\n2. WithUnaryOptions in client/option_unary.go:"
grep -n "func WithUnaryOptions" /app/client/option_unary.go

echo -e "\n3. WithUnaryRPCTimeout:"
grep -n "func WithUnaryRPCTimeout" /app/client/option_unary.go

echo -e "\n4. WithStreamOptions in client/option_stream.go:"
grep -n "func WithStreamOptions" /app/client/option_stream.go

echo -e "\n5. WithStreamRecvTimeout:"
grep -n "func WithStreamRecvTimeout" /app/client/option_stream.go

echo -e "\n6. WithTTHeaderStreamingOptions in client/option_ttstream.go:"
grep -n "func WithTTHeaderStreamingOptions" /app/client/option_ttstream.go

echo -e "\n7. WithRecvTimeout in client/callopt/streamcall:"
grep -n "func WithRecvTimeout" /app/client/callopt/streamcall/streamcall.go
