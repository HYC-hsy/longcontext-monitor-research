
# Check the sep StreamEndpoint signature - it should take ServerStream as parameter, not return it
grep -A2 "type StreamEndpoint" /app/pkg/endpoint/sep/endpoint.go
