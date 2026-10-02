[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;

Get-ChildItem -Path "E:\runs\d720ba89a8e5ad87acb69737\workspace" -Recurse -File | Select-Object FullName, Length | Format-Table -AutoSize
