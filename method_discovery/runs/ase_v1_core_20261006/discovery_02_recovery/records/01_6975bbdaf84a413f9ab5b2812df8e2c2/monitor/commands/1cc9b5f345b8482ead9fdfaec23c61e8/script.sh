
# Check if any new files have been created
cd /app && git status --short 2>/dev/null | head -40
