
# Test the actual implementation in the workspace
cd /app && cat > /tmp/test_actual.go << 'EOF'
package main

import (
	"fmt"
	"github.com/cloudwego/kitex/transport"
)

func main() {
	// Test composite with HESSIAN2
	composite := transport.TTHeader | transport.HESSIAN2
	fmt.Printf("TTHeader | HESSIAN2 (should be 'TTHeader|Hessian2'): %q\n", composite.String())
	
	// Test GRPC | Framed
	composite2 := transport.GRPC | transport.Framed
	fmt.Printf("GRPC | Framed (should be 'Framed|GRPC'): %q\n", composite2.String())
	
	// Test single flag
	fmt.Printf("HESSIAN2 alone (should be 'Hessian2'): %q\n", transport.HESSIAN2.String())
}
EOF
go run /tmp/test_actual.go
