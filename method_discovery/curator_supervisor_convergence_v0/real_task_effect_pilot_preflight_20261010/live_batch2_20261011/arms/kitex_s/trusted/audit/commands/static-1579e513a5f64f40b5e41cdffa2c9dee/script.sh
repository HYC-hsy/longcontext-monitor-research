
# Check if the Task Agent is implementing String() for the right type
echo "=== What TMessageType String() is being added (WRONG for Target 3) ==="
grep -n "func.*TMessageType.*String\|type TMessageType" /app/pkg/protocol/bthrift/apache/thrift.go | head -10
echo "---"
echo "=== Target 3 requires String() on transport.Protocol (CORRECT location) ==="
grep -A 5 "type Protocol" /app/transport/keys.go | head -8
