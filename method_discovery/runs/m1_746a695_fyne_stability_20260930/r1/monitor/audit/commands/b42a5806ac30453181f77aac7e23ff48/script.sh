
# Check T6: Container.RemoveAll, Entry.SetMinRowsVisible, Hyperlink.OnTapped field
grep -n "func.*RemoveAll\|func.*SetMinRowsVisible" /app/container.go /app/widget/entry.go
grep -n "OnTapped.*func()" /app/widget/hyperlink.go | head -2
