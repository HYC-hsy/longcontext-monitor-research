
cd /app && grep -r "type.*App.*struct" --include="*.go" | grep -v vendor | head -20
