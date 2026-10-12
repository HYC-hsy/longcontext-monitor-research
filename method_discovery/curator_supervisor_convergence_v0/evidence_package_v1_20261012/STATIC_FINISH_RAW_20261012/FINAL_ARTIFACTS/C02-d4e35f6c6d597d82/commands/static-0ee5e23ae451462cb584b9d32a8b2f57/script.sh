mkdir -p /tmp/go_check
cd /tmp/go_check
printf '%s\n' 'module offlinecheck' '' 'go 1.18' >go.mod
printf '%s\n' 'package check' 'import "testing"' 'func TestPass(t *testing.T) {}' 'func TestFail(t *testing.T) { t.Fatal("fixture failure") }' 'func TestParent(t *testing.T) { t.Run("child", func(t *testing.T) { t.Skip("fixture skip") }) }' >check_test.go
