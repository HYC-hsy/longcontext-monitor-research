
# Try to build the whole project to see all errors
cd /app
go build . 2>&1 | head -20
