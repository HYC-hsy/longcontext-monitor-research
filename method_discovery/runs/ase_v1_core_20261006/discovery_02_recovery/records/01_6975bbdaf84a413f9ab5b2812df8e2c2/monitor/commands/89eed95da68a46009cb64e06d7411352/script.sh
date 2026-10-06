
# Check EventHandler, CloseCallbackRegister, and GRPCStreamGetter
cd /app && grep -A2 "^type EventHandler\|^type CloseCallbackRegister\|^type GRPCStreamGetter" pkg/streaming/streaming.go
