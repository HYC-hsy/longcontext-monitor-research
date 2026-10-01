
# Check EventHandler fix in streaming.go
grep -A 1 "type EventHandler" /app/pkg/streaming/streaming.go

# Check if stats import was added
grep "pkg/stats" /app/pkg/streaming/streaming.go
