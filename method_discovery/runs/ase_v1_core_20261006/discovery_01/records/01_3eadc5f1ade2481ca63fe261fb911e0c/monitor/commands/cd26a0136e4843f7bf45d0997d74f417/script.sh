
cat > /tmp/test_protocol_fixed.go << 'EOF'
package main
import "fmt"

type Protocol int

const (
	PurePayload Protocol = 0
	TTHeader    Protocol = 2
	Framed      Protocol = 4
	HTTP        Protocol = 8
	GRPC        Protocol = 16
	HESSIAN2    Protocol = 32
	TTHeaderStreaming Protocol = 64
	GRPCStreaming     Protocol = 128
	TTHeaderFramed = TTHeader | Framed
)

const Unknown = "Unknown"

func (tp Protocol) String() string {
	if tp == 0 {
		return "PurePayload"
	}
	flags := []struct {
		bit  Protocol
		name string
	}{
		{TTHeader, "TTHeader"},
		{Framed, "Framed"},
		{HTTP, "HTTP"},
		{GRPC, "GRPC"},
		{HESSIAN2, "Hessian2"},
		{TTHeaderStreaming, "TTHeaderStreaming"},
		{GRPCStreaming, "GRPCStreaming"},
	}
	var parts []string
	remaining := tp
	for _, flag := range flags {
		if tp&flag.bit != 0 {
			parts = append(parts, flag.name)
			remaining &^= flag.bit
		}
	}
	if remaining == 0 && len(parts) > 0 {
		if len(parts) == 1 {
			return parts[0]
		}
		result := ""
		for i, part := range parts {
			if i > 0 {
				result += "|"
			}
			result += part
		}
		return result
	}
	return Unknown
}

func main() {
	fmt.Printf("PurePayload.String() = %q (expected \"PurePayload\")\n", PurePayload.String())
	fmt.Printf("TTHeader.String() = %q (expected \"TTHeader\")\n", TTHeader.String())
	fmt.Printf("Framed.String() = %q (expected \"Framed\")\n", Framed.String())
	fmt.Printf("HESSIAN2.String() = %q (expected \"Hessian2\")\n", HESSIAN2.String())
	fmt.Printf("TTHeaderStreaming.String() = %q (expected \"TTHeaderStreaming\")\n", TTHeaderStreaming.String())
	fmt.Printf("GRPCStreaming.String() = %q (expected \"GRPCStreaming\")\n", GRPCStreaming.String())
	fmt.Printf("TTHeaderFramed.String() = %q (expected \"TTHeader|Framed\")\n", TTHeaderFramed.String())
	fmt.Printf("(GRPC | Framed).String() = %q (expected \"Framed|GRPC\")\n", (GRPC | Framed).String())
}
EOF
cd /tmp && go run test_protocol_fixed.go
