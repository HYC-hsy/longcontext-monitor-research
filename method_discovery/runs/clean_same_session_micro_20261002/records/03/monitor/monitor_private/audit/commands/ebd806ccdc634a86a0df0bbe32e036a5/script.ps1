[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;

# Check what exists in the workspace
Get-ChildItem -Path "E:\runs\16eccbcce795cd83e0a914f9\workspace" -Recurse -File | Select-Object FullName, Length | Format-Table -AutoSize
