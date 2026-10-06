
# Check if EventHandler, CloseCallbackRegister, GRPCStreamGetter were fixed
cd /app && grep -A2 "^type EventHandler\|^type CloseCallbackRegister\|^type GRPCStreamGetter" pkg/streaming/streaming.go
