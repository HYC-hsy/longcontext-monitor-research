
# Continue reading the output from the previous command
echo ""
echo "REQUIREMENT 7: Retry/fallback migration (continued)"
echo "  Checking migration to o.UnaryOptions fields:"
grep -A5 "func WithFailureRetry" /app/client/option.go 2>/dev/null | grep "UnaryOptions"
grep -A5 "func WithBackupRequest" /app/client/option.go 2>/dev/null | grep "UnaryOptions"
grep -A5 "func WithRetryContainer" /app/client/option.go 2>/dev/null | grep "UnaryOptions"
grep -A5 "func WithFallback" /app/client/option.go 2>/dev/null | grep "UnaryOptions"
