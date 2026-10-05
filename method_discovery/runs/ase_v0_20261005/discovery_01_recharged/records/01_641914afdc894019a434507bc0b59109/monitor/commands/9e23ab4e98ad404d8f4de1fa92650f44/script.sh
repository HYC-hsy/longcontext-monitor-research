
# Check where the default transport protocol is set in the codebase
echo "=== TARGET 3 DEFAULT PROTOCOL INVESTIGATION ==="
echo ""
echo "Spec requirement: Default transport protocol should be Framed (not PurePayload)"
echo ""

echo "1. Checking rpcinfo default initialization:"
grep -A5 "func NewRPCConfig\|func newRPCConfig" /app/pkg/rpcinfo/rpcconfig.go 2>/dev/null | head -15

echo ""
echo "2. Checking if transport protocol has a default value:"
grep -B2 -A5 "transport.*Protocol\|transProto.*transport\." /app/pkg/rpcinfo/rpcconfig.go 2>/dev/null | grep -A5 "transport:" | head -10

echo ""
echo "3. Checking client default options:"
grep -n "transport.*=\|TransportProtocol\|defaultTransport" /app/internal/client/option.go 2>/dev/null | head -10

echo ""
echo "4. Check if any file sets Framed as default:"
grep -rn "transport.Framed" /app/pkg/rpcinfo/*.go /app/internal/client/*.go 2>/dev/null | grep -i "default\|initial" | head -5
