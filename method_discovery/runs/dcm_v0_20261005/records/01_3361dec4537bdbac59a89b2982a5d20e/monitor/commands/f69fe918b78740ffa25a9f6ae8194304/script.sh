
# Comprehensive build check - compile the entire codebase
cd /app
go build ./... 2>&1 | head -30
