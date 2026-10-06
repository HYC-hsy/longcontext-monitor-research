
# Check key directories and files mentioned in the task
echo "=== app/ directory ==="
ls /app/app/*.go 2>/dev/null | head -5

echo -e "\n=== theme/ directory ==="
ls /app/theme/*.go 2>/dev/null | head -5

echo -e "\n=== data/binding/ directory ==="
ls /app/data/binding/*.go 2>/dev/null | head -5

echo -e "\n=== widget/ directory ==="
ls /app/widget/*.go 2>/dev/null | head -5

echo -e "\n=== driver/desktop/ directory ==="
ls /app/driver/desktop/*.go 2>/dev/null | head -5

echo -e "\n=== data/validation/ directory ==="
ls /app/data/validation/*.go 2>/dev/null | head -5
