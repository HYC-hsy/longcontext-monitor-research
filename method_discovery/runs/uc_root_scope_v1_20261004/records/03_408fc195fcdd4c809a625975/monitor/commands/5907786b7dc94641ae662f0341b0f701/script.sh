
cd /app && grep -rn "CallOptions" client/ --include="*.go" | grep -i "new\|apply" | head -30
