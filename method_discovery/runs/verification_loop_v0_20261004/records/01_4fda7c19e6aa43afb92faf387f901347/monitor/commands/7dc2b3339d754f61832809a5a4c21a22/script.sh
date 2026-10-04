
# Check where NewAllStrings was implemented
cd /app
find . -name "*.go" -type f -exec grep -l "NewAllStrings" {} \; 2>/dev/null
