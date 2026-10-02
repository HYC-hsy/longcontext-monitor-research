[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;
Get-ChildItem -Path "E:\runs\78d6f30e4a44b2b1ce18ebfe\workspace" -Recurse | Select-Object FullName, Length | Format-Table -AutoSize