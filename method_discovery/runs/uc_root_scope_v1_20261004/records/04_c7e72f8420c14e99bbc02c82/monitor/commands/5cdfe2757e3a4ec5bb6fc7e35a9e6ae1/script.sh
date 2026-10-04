
# Check if the required Target 5 functions exist
echo "=== Checking for Target 5 required function implementations ==="

# 1. Check client/option.go for type aliases and TailOption
if [ -f /app/client/option.go ]; then
    echo "--- client/option.go type aliases ---"
    grep -E "type.*UnaryOption|type.*StreamOption|type.*TTHeaderStreamingOption|func TailOption" /app/client/option.go | head -10
else
    echo "client/option.go not found"
fi

# 2. Check for option_unary.go
if [ -f /app/client/option_unary.go ]; then
    echo -e "\n--- client/option_unary.go exists ---"
    ls -la /app/client/option_unary.go
else
    echo -e "\nclient/option_unary.go NOT FOUND"
fi

# 3. Check for option_stream.go
if [ -f /app/client/option_stream.go ]; then
    echo -e "\n--- client/option_stream.go exists ---"
    ls -la /app/client/option_stream.go
else
    echo -e "\nclient/option_stream.go NOT FOUND"
fi

# 4. Check for option_ttstream.go
if [ -f /app/client/option_ttstream.go ]; then
    echo -e "\n--- client/option_ttstream.go exists ---"
    ls -la /app/client/option_ttstream.go
else
    echo -e "\nclient/option_ttstream.go NOT FOUND"
fi

# 5. Check callopt/streamcall for WithRecvTimeout
echo -e "\n--- Checking callopt/streamcall for WithRecvTimeout ---"
grep -r "func WithRecvTimeout" /app/client/callopt/streamcall/ 2>/dev/null || echo "WithRecvTimeout NOT FOUND"
