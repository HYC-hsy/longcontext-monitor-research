
# Check Target 7: desktop.App interface methods
if [ -f /app/driver/desktop/app.go ]; then
    echo "=== driver/desktop/app.go exists ==="
    grep -A 10 "type App interface" /app/driver/desktop/app.go
else
    echo "ERROR: driver/desktop/app.go does NOT exist"
fi
