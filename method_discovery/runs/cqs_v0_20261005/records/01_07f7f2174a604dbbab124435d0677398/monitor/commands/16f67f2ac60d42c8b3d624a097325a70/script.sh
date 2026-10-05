
# Check app sub-package for metadata functions
echo "=== Checking app sub-package ==="
ls -la /app/app/*.go | grep -E "meta"
echo -e "\n=== Checking widget package for toolbar and hyperlink ==="
ls -la /app/widget/*.go | grep -E "(toolbar|hyperlink|entry)" | head -10
