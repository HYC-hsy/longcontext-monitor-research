
# Check if theme/fromjson.go still has compilation errors
cd /app && go build ./theme 2>&1 | grep -E "(undefined|error)" | head -10
