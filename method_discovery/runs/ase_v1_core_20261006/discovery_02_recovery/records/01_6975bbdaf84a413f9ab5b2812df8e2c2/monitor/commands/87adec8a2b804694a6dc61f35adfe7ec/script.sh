
# Check what test is actually failing in thrift codec
cd /app && go test ./pkg/remote/codec/thrift/... -run TestMarshal 2>&1 | grep -A5 "FAIL\|BasicCodec"
