
cd /app && find . -name "*.go" -type f -exec grep -l "callopt.CallOptions.*RecvTimeout\|RecvTimeout.*callopt" {} \; 2>/dev/null | head -10
