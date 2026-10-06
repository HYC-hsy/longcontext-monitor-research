
# Look for any new directories that might have been created for the targets
ls -la /app/pkg/endpoint/ 2>/dev/null
ls -la /app/client/ | grep -E "(option_unary|option_stream|option_ttstream)" 2>/dev/null || echo "No new option files"
