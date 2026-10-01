
# Check if default was changed from PurePayload to Framed in rpcconfig
grep -n "transport.Framed\|transport.PurePayload" /app/pkg/rpcinfo/rpcconfig.go 2>&1 | head -10
echo "---"
# Look for where protocol is initialized
grep -n "TransportProtocol.*=" /app/pkg/rpcinfo/rpcconfig.go 2>&1 | head -10
