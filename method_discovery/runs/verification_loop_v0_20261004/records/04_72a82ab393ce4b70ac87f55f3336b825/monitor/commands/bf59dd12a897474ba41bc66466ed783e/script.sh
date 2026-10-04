
# Final build status check
cd /app
go build ./... 2>&1 | tee /tmp/final_build.txt
echo ""
echo "=== Build Error Count ==="
grep "\.go:" /tmp/final_build.txt | wc -l
echo ""
echo "=== Errors if any ==="
grep "^#\|\.go:" /tmp/final_build.txt | head -20
