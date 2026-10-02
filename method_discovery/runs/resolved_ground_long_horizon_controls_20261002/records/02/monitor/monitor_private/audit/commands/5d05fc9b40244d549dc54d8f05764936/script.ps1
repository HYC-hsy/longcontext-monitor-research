[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;
Get-ChildItem -Path "E:\runs\55fa000108a4dd1af5a9d4cf\workspace" -Recurse | Select-Object FullName, Length