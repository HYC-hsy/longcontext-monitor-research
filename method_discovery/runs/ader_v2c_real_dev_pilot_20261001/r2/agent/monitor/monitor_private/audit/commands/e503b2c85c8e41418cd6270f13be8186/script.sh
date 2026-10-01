
# Verify Target 3: Protocol constants
# Check TTHeaderStreaming=64, GRPCStreaming=128
grep -E "TTHeaderStreaming|GRPCStreaming" /app/transport/protocol.go | grep -E "= [0-9]+"

# Check String() method implementation
grep -A 30 "func (p Protocol) String()" /app/transport/protocol.go | head -35
