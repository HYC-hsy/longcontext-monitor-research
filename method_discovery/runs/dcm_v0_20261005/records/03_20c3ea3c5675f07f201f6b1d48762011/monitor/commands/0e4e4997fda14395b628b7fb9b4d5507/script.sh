
# Check what type aliases were added to client/option.go
cd /app && grep -n "type.*Option.*=" client/option.go | grep -E "(Unary|Stream|TTHeader)" | head -10
