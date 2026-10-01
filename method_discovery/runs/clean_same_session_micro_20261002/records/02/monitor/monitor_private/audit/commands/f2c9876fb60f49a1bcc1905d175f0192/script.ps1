[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;

# Check workspace structure
Get-ChildItem -Path "E:\runs\91893ddd44daf12057ac4974\workspace" -Recurse | Select-Object FullName, Length
