
# Wait for build and check if it completed successfully
sleep 3
# Check build status
ps aux | grep "go build" | grep -v grep || echo "Build completed or not running"
