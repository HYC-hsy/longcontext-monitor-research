
# Check if there's any code setting Framed as default
grep -r "Framed.*default\|default.*Framed" /app --include="*.go" 2>/dev/null | head -10
echo "---"
# Check for PurePayload being replaced with Framed in initialization
grep -r "PurePayload\|Protocol.*=.*0\|Protocol.*=.*Framed" /app/client /app/server --include="*.go" 2>/dev/null | head -10
