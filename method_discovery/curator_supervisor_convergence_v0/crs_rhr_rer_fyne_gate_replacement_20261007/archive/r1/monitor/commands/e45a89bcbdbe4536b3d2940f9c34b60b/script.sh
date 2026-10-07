
# Check for key directories and files mentioned in requirements
echo "=== Checking root package ==="
ls -la /app/*.go | grep -E "(app\.go|container\.go|menu\.go)" || echo "Not found"

echo -e "\n=== Checking app sub-package ==="
ls -d /app/app 2>/dev/null && ls /app/app/*.go | head -5 || echo "Not found"

echo -e "\n=== Checking theme package ==="
ls -d /app/theme 2>/dev/null && ls /app/theme/*.go | head -5 || echo "Not found"

echo -e "\n=== Checking data/binding package ==="
ls -d /app/data/binding 2>/dev/null && ls /app/data/binding/*.go | head -5 || echo "Not found"

echo -e "\n=== Checking data/validation package ==="
ls -d /app/data/validation 2>/dev/null && ls /app/data/validation/*.go | head -5 || echo "Not found"

echo -e "\n=== Checking widget package ==="
ls -d /app/widget 2>/dev/null && ls /app/widget/*.go | head -5 || echo "Not found"

echo -e "\n=== Checking driver/desktop package ==="
ls -d /app/driver/desktop 2>/dev/null && ls /app/driver/desktop/*.go || echo "Not found"
