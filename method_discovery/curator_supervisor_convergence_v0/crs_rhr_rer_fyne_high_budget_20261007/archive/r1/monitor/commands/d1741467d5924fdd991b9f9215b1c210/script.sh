
# Verify key signatures match specifications
cd /app

echo "=== Checking FromJSON signature ==="
grep -n "func FromJSON" theme/json.go | head -3

echo -e "\n=== Checking StringToStringWithFormat ==="
grep -n "func StringToStringWithFormat" data/binding/sprintf.go

echo -e "\n=== Checking NewAllStrings signature ==="
grep -n "func NewAllStrings" data/validation/all.go

echo -e "\n=== Checking desktop.App methods ==="
grep -A 1 "SetSystemTray" driver/desktop/app.go
