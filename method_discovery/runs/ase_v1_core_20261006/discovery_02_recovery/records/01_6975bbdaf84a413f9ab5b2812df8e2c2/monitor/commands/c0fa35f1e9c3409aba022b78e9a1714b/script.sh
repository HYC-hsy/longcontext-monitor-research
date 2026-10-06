
# Check the CloseCallbackRegister, GRPCStreamGetter, and EventHandler definitions
cd /app && grep -A3 "type CloseCallbackRegister\|type GRPCStreamGetter\|type EventHandler" pkg/streaming/streaming.go
