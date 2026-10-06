
# Quick verification of the two corrected specifications
echo "=== Verifying corrected specifications ==="
echo ""
echo "Target 1: SetMetadata signature"
grep "^func SetMetadata" /app/app/meta.go
echo ""
echo "Target 7: desktop.App interface methods"
grep -A 1 "SetSystemTray" /app/driver/desktop/app.go
