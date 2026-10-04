
# Check what the original requirement says about UnaryOptions
cd /app
echo "Checking if UnaryOptions is meant to be an alias or a new field..."
grep -n "UnaryOption.*=.*client\\.UnaryOption" client/option.go
echo ""
echo "Checking existing internal/client Options struct:"
grep -A50 "type Options struct" internal/client/option.go | head -60
