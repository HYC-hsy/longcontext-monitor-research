
# Search for all types that might implement the App interface
# Look for methods that match App interface signatures
cd /app
grep -r "func.*Metadata()" --include="*.go" | head -20
