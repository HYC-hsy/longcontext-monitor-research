
# Check what test actually failed
cd /app && go test ./pkg/remote/codec/thrift/... -v 2>&1 | grep -E "(FAIL|PASS|RUN.*Basic)" | tail -20
