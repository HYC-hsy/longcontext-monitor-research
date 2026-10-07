
# Check if RemoveAll method exists in container.go
grep -n "func.*RemoveAll\|Add(add CanvasObject)" /app/container.go | head -10
