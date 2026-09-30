
# Check the original protocol values from git history
cd /app && git show HEAD:transport/keys.go | grep -A 15 "const ("
