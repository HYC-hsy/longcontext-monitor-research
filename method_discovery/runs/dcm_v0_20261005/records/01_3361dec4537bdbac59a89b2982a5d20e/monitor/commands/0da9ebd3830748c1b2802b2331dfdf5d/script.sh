
# Check the result of building the theme package
cd /app && go build ./theme/ 2>&1 | head -20
