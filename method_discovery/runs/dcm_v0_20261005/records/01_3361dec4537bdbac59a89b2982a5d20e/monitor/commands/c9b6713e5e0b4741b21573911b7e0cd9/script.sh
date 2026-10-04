
# Look for other implementations of the App interface by searching for methods
cd /app
grep -r "func.*Metadata().*AppMetadata" --include="*.go" | grep -v "_test.go"
