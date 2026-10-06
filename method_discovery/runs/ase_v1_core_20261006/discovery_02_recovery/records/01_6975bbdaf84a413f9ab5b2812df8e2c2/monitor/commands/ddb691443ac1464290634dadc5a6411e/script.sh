
# Check EventHandler, CloseCallbackRegister, GRPCStreamGetter definitions
cd /app && grep -B1 -A2 "type EventHandler\|type CloseCallbackRegister\|type GRPCStreamGetter" pkg/streaming/streaming.go
