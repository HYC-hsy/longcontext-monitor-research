
# Check if driver/desktop/app.go exists and has both required methods
if [ -f /app/driver/desktop/app.go ]; then
  echo "=== driver/desktop/app.go contents ==="
  cat /app/driver/desktop/app.go
else
  echo "File not found"
fi
