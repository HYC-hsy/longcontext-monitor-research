
# Check the actual protocol constant values
cd /app && go run -C transport << 'EOF'
package main
import (
	"fmt"
	"github.com/cloudwego/kitex/transport"
)
func main() {
	fmt.Printf("PurePayload = %d\n", transport.PurePayload)
	fmt.Printf("TTHeader = %d\n", transport.TTHeader)
	fmt.Printf("Framed = %d\n", transport.Framed)
	fmt.Printf("HTTP = %d\n", transport.HTTP)
	fmt.Printf("GRPC = %d\n", transport.GRPC)
	fmt.Printf("HESSIAN2 = %d\n", transport.HESSIAN2)
	fmt.Printf("TTHeaderStreaming = %d\n", transport.TTHeaderStreaming)
	fmt.Printf("GRPCStreaming = %d\n", transport.GRPCStreaming)
	fmt.Printf("TTHeaderFramed = %d\n", transport.TTHeaderFramed)
	fmt.Printf("\n")
	fmt.Printf("TTHeaderFramed.String() = %q\n", transport.TTHeaderFramed.String())
	fmt.Printf("TTHeaderStreaming.String() = %q\n", transport.TTHeaderStreaming.String())
}
EOF
