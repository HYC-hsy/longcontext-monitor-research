
# Find all types that implement App interface methods
cd /app
# Search for Run() method implementations (unique to App)
grep -r "func.*Run()" --include="*.go" | grep -v "func Run" | grep -v "// " | grep "receiver" -A 1 | head -30
