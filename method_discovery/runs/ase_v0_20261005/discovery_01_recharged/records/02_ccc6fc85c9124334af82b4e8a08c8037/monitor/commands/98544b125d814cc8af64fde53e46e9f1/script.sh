
# Check if there are other App implementations that need updating
grep -r "type.*App.*struct" /app/app/*.go /app/internal/app/*.go /app/driver/*/app*.go 2>/dev/null | head -20
