
# TARGET 6 VERIFICATION: Check exact error format requirement
echo "=== Target 6: Checking if error format matches EXACT task requirement ==="
echo "Task requires: fmt.Errorf(\"%s or invalid frame (first4Bytes=%#x, second4Bytes=%#x)\", http2.ErrFrameTooLarge, buf[:4], buf[4:8])"
echo "Condition: When frame size exceeds maxReadSize"
echo ""
echo "Checking ReadFrame method around fh.Length > fr.maxReadSize:"
grep -A 5 "if fh.Length > fr.maxReadSize" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
