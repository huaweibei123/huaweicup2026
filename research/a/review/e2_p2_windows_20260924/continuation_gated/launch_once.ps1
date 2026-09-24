# STATIC PROPOSAL ONLY. Call only after an explicit approval of this fixed bundle.
# Parsing this file is permitted during review; executing it is not.
param(
    [Parameter(Mandatory=$true)][string]$ApprovalReference,
    [Parameter(Mandatory=$true)][string]$AuthorizedCommit,
    [Parameter(Mandatory=$true)][string]$ExpectedBundleHash,
    [Parameter(Mandatory=$true)][string]$EvidenceName
)

# Capture before approval preparation, identity reads or launching any Python.
$cdeOuterUtc = [DateTimeOffset]::UtcNow.ToString('o')
$cdeOuterMono = [Diagnostics.Stopwatch]::GetTimestamp()
$cdeOuterFrequency = [Diagnostics.Stopwatch]::Frequency
$cdeOuterTick = [Environment]::TickCount64
$ErrorActionPreference = 'Stop'
$cdeProcess = $null
$cdeDirectory = $null
$cdeOuter = [ordered]@{
    outer_t0_utc=$cdeOuterUtc; outer_t0_stopwatch=$cdeOuterMono;
    stopwatch_frequency=$cdeOuterFrequency; outer_t0_tick64_ms=$cdeOuterTick;
    authorized_commit=$AuthorizedCommit; approval_reference=$ApprovalReference;
    approved_bundle_hash=$ExpectedBundleHash; wall_cap_seconds=900;
    evaluation_cutoff_seconds=300; parent_invocations=0; forced_parent_cleanup=$false;
    status='preparing'
}
try {
    if ($EvidenceName -notmatch '^[a-z0-9][a-z0-9-]{8,90}$') { throw 'Invalid evidence directory name' }
    if ($AuthorizedCommit -notmatch '^[a-f0-9]{40}$' -or $ExpectedBundleHash -notmatch '^[a-f0-9]{64}$') {
        throw 'Full approved commit and bundle hash required'
    }
    if ($ApprovalReference -notmatch '^https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-[0-9]+$') {
        throw 'Exact new approval reference required; this script does not grant authorization'
    }
    $cdeCandidate = Join-Path $env:LOCALAPPDATA ('CodexEvidence/' + $EvidenceName)
    if (Test-Path -LiteralPath $cdeCandidate) { throw 'Fresh directory already exists; no retry' }
    New-Item -ItemType Directory -Path $cdeCandidate | Out-Null
    $cdeDirectory = $cdeCandidate
    $cdeOuter | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $cdeDirectory 'outer.json') -Encoding utf8NoBOM
    $cdeRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../../..'))
    $cdeHead = & git -C $cdeRoot rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $cdeHead.Trim() -ne $AuthorizedCommit) { throw 'Unapproved HEAD' }
    $cdeStatus = & git -C $cdeRoot status --porcelain
    if ($LASTEXITCODE -ne 0 -or $cdeStatus) { throw 'Dirty/unavailable working tree' }
    $cdeContract = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'contract.json') -Raw | ConvertFrom-Json
    $cdeApproval = [ordered]@{execute_approved=$true; schema=$cdeContract.schema;
        caps=$cdeContract.caps; reference=$ApprovalReference; authorized_commit=$AuthorizedCommit;
        source_bundle_sha256=$ExpectedBundleHash}
    $cdeApprovalPath = Join-Path $cdeDirectory 'approval.json'
    $cdeOuterPath = Join-Path $cdeDirectory 'outer.json'
    $cdeApproval | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $cdeApprovalPath -Encoding utf8NoBOM
    $cdeBeforeParent = ([Diagnostics.Stopwatch]::GetTimestamp() - $cdeOuterMono) / $cdeOuterFrequency
    if ($cdeBeforeParent -ge 90) { throw 'Outer preparation deadline' }
    $cdeOuter.pre_parent_wall_seconds = $cdeBeforeParent
    $cdeOuter.parent_invocations = 1
    $cdeOuter.status = 'parent_start_requested'
    $cdeOuter | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $cdeOuterPath -Encoding utf8NoBOM
    # Windows paths cannot contain double quotes; all path arguments end in a
    # file/directory name, so no trailing backslash escapes the closing quote.
    $cdeArguments = @('-I', '-B', ('"' + (Join-Path $PSScriptRoot 'run_gated_continuation.py') + '"'),
        '--private', ('"' + (Join-Path $cdeDirectory 'run') + '"'),
        '--approval', ('"' + $cdeApprovalPath + '"'), '--outer', ('"' + $cdeOuterPath + '"')) -join ' '
    $cdeProcess = Start-Process -FilePath (Join-Path $cdeRoot '.venv/Scripts/python.exe') -ArgumentList $cdeArguments `
        -WorkingDirectory $cdeRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $cdeDirectory 'parent.stdout.raw') `
        -RedirectStandardError (Join-Path $cdeDirectory 'parent.stderr.raw')
    $cdeOuter.parent_launcher_pid = $cdeProcess.Id
    $cdeWaitMs = [Math]::Max(0, [int]((310 - (([Diagnostics.Stopwatch]::GetTimestamp() - $cdeOuterMono) / $cdeOuterFrequency)) * 1000))
    if (-not $cdeProcess.WaitForExit($cdeWaitMs)) {
        $cdeOuter.forced_parent_cleanup = $true
        $cdeProcess.Kill($true)
        if (-not $cdeProcess.WaitForExit(10000)) { throw 'Parent tree cleanup not confirmed' }
        throw 'Parent exceeded outer control/cleanup deadline; no retry'
    }
    $cdeProcess.Refresh()
    $cdeOuter.parent_exit_code = $cdeProcess.ExitCode
    $cdeOuter.status = 'parent_ended'
} catch {
    $cdeOuter.status = 'outer_failure'
    $cdeOuter.error = $_.ToString()
} finally {
    # An exception after Start-Process must not leave the parent outside its
    # ordinary deadline path. This is cleanup of that same attempt, never retry.
    if ($cdeProcess) {
        try {
            if (-not $cdeProcess.HasExited) {
                $cdeOuter.forced_parent_cleanup = $true
                $cdeProcess.Kill($true)
                $cdeOuter.parent_cleanup_confirmed = $cdeProcess.WaitForExit(10000)
                $cdeOuter.status = 'outer_failure'
            }
        } catch {
            $cdeOuter.parent_cleanup_error = $_.ToString()
            $cdeOuter.status = 'outer_failure'
        }
    }
    $cdeOuter.end_utc = [DateTimeOffset]::UtcNow.ToString('o')
    $cdeOuter.end_stopwatch = [Diagnostics.Stopwatch]::GetTimestamp()
    $cdeOuter.parent_and_preparation_wall_seconds = ($cdeOuter.end_stopwatch - $cdeOuterMono) / $cdeOuterFrequency
    if ($cdeDirectory) {
        $cdeOuter | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $cdeDirectory 'outer.json') -Encoding utf8NoBOM
    }
    $cdeOuter | ConvertTo-Json -Depth 20
    if ($cdeProcess) { $cdeProcess.Dispose() }
}
if ($cdeOuter.status -ne 'parent_ended' -or $cdeOuter.parent_exit_code -ne 0) { exit 1 }
exit 0
