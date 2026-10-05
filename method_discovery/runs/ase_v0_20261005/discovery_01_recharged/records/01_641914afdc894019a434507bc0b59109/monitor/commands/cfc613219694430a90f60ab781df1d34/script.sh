
# Check Target 3 default protocol change requirement
echo "=== TARGET 3 DEFAULT PROTOCOL VERIFICATION ==="
echo ""
echo "Spec requirement: 'The default transport protocol for new RPC configurations"
echo "                   should be transport.Framed instead of transport.PurePayload (0)'"
echo ""
echo "Checking where default protocol is set:"
echo ""

# Check in client initialization
echo "1. Client default protocol:"
grep -rn "default.*protocol\|PurePayload.*0\|Framed" /app/internal/client/option.go 2>/dev/null | grep -v "func\|//" | head -10

echo ""
echo "2. Codec default protocol selection:"
grep -n "PurePayload\|transProto.*=" /app/pkg/remote/codec/default_codec.go 2>/dev/null | head -15

echo ""
echo "3. RPC config initialization:"
grep -rn "SetTransportProtocol\|transport.Framed\|transport.PurePayload" /app/pkg/rpcinfo/*.go 2>/dev/null | head -10

echo ""
echo "Note: The spec requires the DEFAULT to be Framed, not PurePayload"
echo "      This means new clients/servers should use Framed unless explicitly configured otherwise"
