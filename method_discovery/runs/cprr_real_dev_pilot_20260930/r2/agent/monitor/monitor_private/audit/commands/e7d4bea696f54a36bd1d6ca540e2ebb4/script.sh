
# Get comprehensive view of what files have been modified or created
cd /app && git status --short

# Check for all App interface implementations that might need Metadata()
grep -r "func.*Metadata()" /app --include="*.go" | grep -v ".git" | grep -v "//.*Metadata()"
