
cd /app
# Check the actual test results from the most recent run
go test ./data/binding ./data/validation ./driver/desktop ./theme 2>&1 | tail -30
