param(
    [int]$OffPid,
    [string]$Manifest,
    [string]$WorkingDirectory,
    [string]$LogDirectory,
    [string]$OnRunId
)
$ErrorActionPreference = 'Continue'
while (Get-Process -Id $OffPid -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds 30
}
# Give the runner a moment to release its shared OTEL container.
for ($i = 0; $i -lt 20; $i++) {
    $collector = docker ps --filter name=m12-natural-ga-otel --format '{{.Names}}'
    if (-not $collector) { break }
    Start-Sleep -Seconds 15
}
$python = 'D:\python\envs\ga_bench\python.exe'
$args = @(
    'scripts/run_ultralong_m12_proofs.py', '--experiment-manifest', $Manifest,
    '--source', 'roadmapbench', '--task-id', 'fyn-2.2.0-roadmap',
    '--llm-no', '0', '--max-agent-seconds', '10000', '--run-id', $OnRunId
)
New-Item -ItemType Directory -Force $LogDirectory | Out-Null
Start-Process -FilePath $python -ArgumentList $args -WorkingDirectory $WorkingDirectory `
    -RedirectStandardOutput (Join-Path $LogDirectory 'c_on.stdout.log') `
    -RedirectStandardError (Join-Path $LogDirectory 'c_on.stderr.log')
