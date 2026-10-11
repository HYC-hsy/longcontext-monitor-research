
# Find all Protocol constant definitions
grep -n "const.*=" /app/transport/*.go 2>/dev/null | grep -E "TTHeader|Framed|GRPC|PurePayload" | head -20
