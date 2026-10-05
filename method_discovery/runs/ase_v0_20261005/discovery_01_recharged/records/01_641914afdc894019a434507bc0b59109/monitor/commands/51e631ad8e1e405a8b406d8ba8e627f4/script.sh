
# Check if there are any .monitor files or work indicators
find /app -name "*.monitor" -o -name ".work*" -o -name "TODO*" 2>/dev/null | head -20
