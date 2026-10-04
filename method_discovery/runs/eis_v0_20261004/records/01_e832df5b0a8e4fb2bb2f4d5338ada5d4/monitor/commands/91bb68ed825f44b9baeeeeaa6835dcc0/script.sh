
# Check if themedtestapp.go implements App interface
grep -E "(type.*testApp|var _ fyne.App|func \(.*testApp\))" /app/theme/themedtestapp.go | head -20
