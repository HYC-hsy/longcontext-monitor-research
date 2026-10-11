
# Check if any Target 5 functions have been added
echo "Checking for Target 5 implementation:"
ls -la /app/client/option_*.go 2>/dev/null | grep -v "test\|advanced\|categories"
echo "---"
grep -n "WithUnaryRPCTimeout\|WithStreamRecvTimeout\|TailOption" /app/client/*.go 2>/dev/null | head -5 || echo "Target 5 functions still missing"
