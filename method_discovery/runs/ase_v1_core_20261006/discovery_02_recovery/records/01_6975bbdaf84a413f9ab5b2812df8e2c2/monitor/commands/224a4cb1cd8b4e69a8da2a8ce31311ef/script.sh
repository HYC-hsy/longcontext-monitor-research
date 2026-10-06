
# Count how many of the 6 required streaming types exist
cd /app && echo "Required types:"
echo "ServerStreamingClient[Res]: $(grep -c 'type ServerStreamingClient\[' pkg/streaming/streaming.go || echo 0)"
echo "ServerStreamingServer[Res]: $(grep -c 'type ServerStreamingServer\[' pkg/streaming/streaming.go || echo 0)"
echo "ClientStreamingClient[Req,Res]: $(grep -c 'type ClientStreamingClient\[' pkg/streaming/streaming.go || echo 0)"
echo "ClientStreamingServer[Req,Res]: $(grep -c 'type ClientStreamingServer\[' pkg/streaming/streaming.go || echo 0)"
echo "BidiStreamingClient[Req,Res]: $(grep -c 'type BidiStreamingClient\[' pkg/streaming/streaming.go || echo 0)"
echo "BidiStreamingServer[Req,Res]: $(grep -c 'type BidiStreamingServer\[' pkg/streaming/streaming.go || echo 0)"
