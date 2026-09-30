
# Check for files that might have been modified for the targets
cd /app
find . -name "meta.go" -o -name "sprintf.go" -o -name "all.go" | grep -E "(app/meta|binding/sprintf|validation/all)"
