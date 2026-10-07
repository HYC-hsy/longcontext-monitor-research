$ErrorActionPreference = 'Stop'
$repo = 'E:\longcontext-cqs-v0-20261005'
$slot = 'crs-v01-fyne-mechanism-gate-b-only-r1-infra-replacement-2'
$runDir = Join-Path 'E:\runs' ($slot + '-terminal')
New-Item -ItemType Directory -Path $runDir -ErrorAction Stop | Out-Null
$log = Join-Path $runDir 'visible_runner.log'
Set-Location -LiteralPath $repo
Write-Host "CRS Fyne run: $slot"
Write-Host "Runner log: $log"
Write-Host 'One authorized trial only. This terminal remains open after the run.'
try {
    & python -u -m method_discovery.curator_supervisor_convergence_v0.crs_v01_fyne_gate_infra_replacement2_20261007.launch --authorization 'E:\crs_fyne_gate_private_20261007\AUTHORIZATION_REPLACEMENT2.json' 2>&1 | Tee-Object -FilePath $log
    $code = $LASTEXITCODE
    Write-Host "RUNNER_EXIT_CODE=$code"
} catch {
    Write-Host "RUNNER_EXCEPTION=$($_.Exception.GetType().FullName): $($_.Exception.Message)"
}
