param(
  [string]$OutputRoot = 'E:\LongContext\long_context_bench\output\ader_v2c_real_dev_pilot_20261001',
  [string]$ArchiveRoot = 'E:\LongContext\method_discovery\runs\ader_v2c_real_dev_pilot_20261001'
)
$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
if (-not (Test-Path -LiteralPath $ArchiveRoot)) { New-Item -ItemType Directory -Path $ArchiveRoot | Out-Null }
$archiveRootResolved = (Resolve-Path -LiteralPath $ArchiveRoot).Path

function Copy-RawFile([string]$from, [string]$to) {
  $parent = Split-Path -Parent $to
  if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  if (-not (Test-Path -LiteralPath $to)) { Copy-Item -LiteralPath $from -Destination $to }
  $a = (Get-FileHash -LiteralPath $from -Algorithm SHA256).Hash
  $b = (Get-FileHash -LiteralPath $to -Algorithm SHA256).Hash
  if ($a -ne $b) { throw "raw copy hash mismatch: $from" }
}

foreach ($number in 1..2) {
  $suffix = '{0:D2}' -f $number
  $run = "ader-v2c-real-dev-pilot-20261001-$suffix"
  $job = Join-Path $sourceRoot "jobs/$run"
  if (-not (Test-Path -LiteralPath $job)) { continue }
  $trials = @(Get-ChildItem -LiteralPath $job -Directory)
  if ($trials.Count -ne 1) { throw "expected one trial for $run" }
  $trial = $trials[0].FullName
  $dest = Join-Path $archiveRootResolved "r$number"
  if (-not (Test-Path -LiteralPath $dest)) { New-Item -ItemType Directory -Path $dest | Out-Null }
  foreach ($name in @('config.json','lock.json','result.json','trial.log')) {
    $p = Join-Path $trial $name
    if (Test-Path -LiteralPath $p) { Copy-RawFile $p (Join-Path $dest "trial/$name") }
  }
  foreach ($name in @('job.log','job_config.json','job_result.json','launcher_stdout.log','launcher_stderr.log')) {
    $p = Join-Path $job $name
    if (Test-Path -LiteralPath $p) { Copy-RawFile $p (Join-Path $dest "job/$name") }
  }
  $agent = Join-Path $trial 'agent'
  foreach ($p in Get-ChildItem -LiteralPath $agent -File) {
    Copy-RawFile $p.FullName (Join-Path $dest "agent/$($p.Name)")
  }
  $monitor = Join-Path $agent 'monitor'
  foreach ($p in Get-ChildItem -LiteralPath $monitor -File) {
    Copy-RawFile $p.FullName (Join-Path $dest "agent/monitor/$($p.Name)")
  }
  foreach ($sub in @('task_evidence','monitor_private/audit/commands')) {
    $base = Join-Path $monitor $sub
    if (-not (Test-Path -LiteralPath $base)) { continue }
    foreach ($p in Get-ChildItem -LiteralPath $base -Recurse -File -ErrorAction SilentlyContinue) {
      $rel = $p.FullName.Substring($trial.Length + 1)
      Copy-RawFile $p.FullName (Join-Path $dest $rel)
    }
  }
  $private = Join-Path $monitor 'monitor_private'
  foreach ($p in Get-ChildItem -LiteralPath $private -File) {
    Copy-RawFile $p.FullName (Join-Path $dest "agent/monitor/monitor_private/$($p.Name)")
  }
  $audit = Join-Path $private 'audit'
  foreach ($p in Get-ChildItem -LiteralPath $audit -File) {
    Copy-RawFile $p.FullName (Join-Path $dest "agent/monitor/monitor_private/audit/$($p.Name)")
  }
  foreach ($checkpoint in Get-ChildItem -LiteralPath (Join-Path $audit 'live_checkpoints') -Directory -ErrorAction SilentlyContinue) {
    foreach ($name in @('complete.json','identity.json','manifest.json','request.json')) {
      $p = Join-Path $checkpoint.FullName $name
      if (Test-Path -LiteralPath $p) { Copy-RawFile $p (Join-Path $dest "checkpoint_metadata/$($checkpoint.Name)/$name") }
    }
  }
  foreach ($sub in @('verifier','artifacts')) {
    $base = Join-Path $trial $sub
    if (-not (Test-Path -LiteralPath $base)) { continue }
    foreach ($p in Get-ChildItem -LiteralPath $base -Recurse -File -ErrorAction SilentlyContinue) {
      $rel = $p.FullName.Substring($trial.Length + 1)
      Copy-RawFile $p.FullName (Join-Path $dest $rel)
    }
  }
  foreach ($sub in @('runs','source_inputs','isolated_bundles')) {
    $base = Join-Path $sourceRoot "$sub/$run"
    if (-not (Test-Path -LiteralPath $base)) { continue }
    if ($sub -eq 'runs') {
      foreach ($p in Get-ChildItem -LiteralPath $base -File) { Copy-RawFile $p.FullName (Join-Path $dest "proof/$($p.Name)") }
    } elseif ($sub -eq 'source_inputs') {
      foreach ($name in @('source_identity.json','result.json')) {
        $p = Join-Path $base $name
        if (Test-Path -LiteralPath $p) { Copy-RawFile $p (Join-Path $dest "source_identity/$name") }
      }
    } else {
      $p = Join-Path $base 'isolation_identity.json'
      Copy-RawFile $p (Join-Path $dest 'source_identity/isolation_identity.json')
    }
  }
}

$index = @()
foreach ($p in Get-ChildItem -LiteralPath $archiveRootResolved -Recurse -File) {
  if ($p.Name -eq 'RAW_FILE_MANIFEST.json') { continue }
  $index += [pscustomobject]@{ path = $p.FullName.Substring($archiveRootResolved.Length + 1).Replace('\','/'); bytes = $p.Length; sha256 = (Get-FileHash -LiteralPath $p.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
}
[System.IO.File]::WriteAllText((Join-Path $archiveRootResolved 'RAW_FILE_MANIFEST.json'),
  ($index | ConvertTo-Json -Depth 4), [System.Text.UTF8Encoding]::new($false))
Write-Output "archived_files=$($index.Count)"
