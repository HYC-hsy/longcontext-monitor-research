
# Try to compile again to see current errors
cd /app && go build ./theme 2>&1 | head -20
