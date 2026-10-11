
# Final verification: Check if the fields exist in the OLD location (client.Options)
echo "=== Checking OLD field locations in client.Options struct ==="
grep -A 30 "^type Options struct" /app/internal/client/option.go | grep -E "Fallback|RetryWithResult|RetryContainer|RetryMethodPolicies" | head -10
