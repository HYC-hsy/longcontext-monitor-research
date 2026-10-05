
# Try a quick build check to see if there are compilation errors
cd /app && go build ./... 2>&1 | head -50
