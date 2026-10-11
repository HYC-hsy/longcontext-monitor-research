
# Search for Protocol type definition more broadly
grep -rn "type Protocol" /app --include="*.go" 2>/dev/null | grep -v "test\|ProtocolInfo\|ProtocolError" | head -10
