
# Check if internal/client.Options has UnaryOptions field
grep -A 30 "type Options struct" /app/internal/client/option.go | head -40
