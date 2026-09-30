
# Check all target areas
echo "=== Target 1: AppMetadata ==="
ls -la /app/app/meta.go 2>&1 | head -1

echo -e "\n=== Target 2: JSON Theme ==="
find /app/theme -name "*.go" -type f 2>/dev/null | head -5

echo -e "\n=== Target 3: Data Binding Sprintf ==="
ls -la /app/data/binding/sprintf.go 2>&1 | head -1

echo -e "\n=== Target 4: Menu ==="
grep -n "type MenuItem struct" /app/menu.go 2>&1 | head -5

echo -e "\n=== Target 5: Toolbar ==="
ls -la /app/widget/toolbar.go 2>&1 | head -1

echo -e "\n=== Target 6: Container/Widget improvements ==="
ls -la /app/container.go 2>&1 | head -1
ls -la /app/widget/hyperlink.go 2>&1 | head -1
ls -la /app/widget/entry.go 2>&1 | head -1
ls -la /app/data/validation/all.go 2>&1 | head -1

echo -e "\n=== Target 7: Desktop App ==="
ls -la /app/driver/desktop/app.go 2>&1 | head -1
