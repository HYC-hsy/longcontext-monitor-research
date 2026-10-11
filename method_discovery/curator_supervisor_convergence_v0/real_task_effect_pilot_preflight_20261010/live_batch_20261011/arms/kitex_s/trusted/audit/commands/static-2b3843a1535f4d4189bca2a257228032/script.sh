
# Check if deprecated.go exists
if [ -f /app/pkg/endpoint/deprecated.go ]; then
    echo "deprecated.go EXISTS"
else
    echo "deprecated.go DOES NOT EXIST"
fi

# Check if UnaryEndpoint type exists in endpoint.go
grep -n "UnaryEndpoint\|UnaryMiddleware\|UnaryChain" /app/pkg/endpoint/endpoint.go || echo "No Unary types found"
