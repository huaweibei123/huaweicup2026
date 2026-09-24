param([Parameter(Mandatory=$true)][string]$ApprovalPath,
      [Parameter(Mandatory=$true)][string]$EvidenceName)

# Preparation artifact only. This script has NOT been invoked, including --help.
# Reflection.Emit supplies P/Invoke declarations without a compiler/build process.
$e2T0Utc = [DateTimeOffset]::UtcNow.ToString('o')
$e2T0Qpc = [Diagnostics.Stopwatch]::GetTimestamp()
$e2Frequency = [Diagnostics.Stopwatch]::Frequency
function E2-Elapsed { ([Diagnostics.Stopwatch]::GetTimestamp()-$e2T0Qpc)/$e2Frequency }
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 8) { throw 'Only the pinned Windows x64 layout is proposed' }
$e2Here = [IO.Path]::GetFullPath($PSScriptRoot)
$e2Root = [IO.Path]::GetFullPath((Join-Path $e2Here '../../../..'))
$e2Approval = Get-Content -LiteralPath $ApprovalPath -Raw | ConvertFrom-Json
if ($e2Approval.approved -ne $true -or $e2Approval.execution_enabled -ne $true -or
    $e2Approval.runtime_review_closed -ne $true -or -not $e2Approval.approval_reference) {
    throw 'No approved execution window; driver preparation does not authorize running'
}
$e2Contract = Get-Content -LiteralPath (Join-Path $e2Here 'contract.json') -Raw | ConvertFrom-Json
if ($e2Contract.execution_blockers.Count -ne 0) { throw 'Driver preparation checkpoint still has static execution blockers' }
if ($EvidenceName -notmatch '^[a-z0-9][a-z0-9-]{5,80}$') { throw 'Invalid evidence directory name' }
$e2Manifest = Get-Content -LiteralPath (Join-Path $e2Here 'sources.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath (Join-Path $e2Here 'sources.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    $e2Approval.sources_sha256) { throw 'Approval source manifest mismatch' }
foreach ($e2Property in $e2Manifest.driver_files.PSObject.Properties) {
    if ((E2-Elapsed) -ge 90) { throw 'Preparation deadline while checking driver inputs' }
    $e2ActualHash = (Get-FileHash -LiteralPath (Join-Path $e2Here $e2Property.Name) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($e2ActualHash -ne $e2Property.Value) { throw "Driver identity mismatch: $($e2Property.Name)" }
}
if ($e2Approval.driver_bundle_sha256 -ne $e2Manifest.driver_bundle_sha256) { throw 'Approval bundle mismatch' }
# Direct file checks after T0; no Git or other metadata subprocess is created.
$e2DotGit=Join-Path $e2Root '.git'
if ([IO.Directory]::Exists($e2DotGit)) { $e2GitDir=$e2DotGit }
else {
    $e2Pointer=[IO.File]::ReadAllText($e2DotGit).Trim()
    if ($e2Pointer -notmatch '^gitdir: (.+)$') { throw 'Unsupported gitdir pointer' }
    $e2GitDir=[IO.Path]::GetFullPath([IO.Path]::Combine($e2Root,$Matches[1]))
}
$e2Common=$e2GitDir
if ([IO.File]::Exists((Join-Path $e2GitDir 'commondir'))) {
    $e2Common=[IO.Path]::GetFullPath([IO.Path]::Combine($e2GitDir,([IO.File]::ReadAllText((Join-Path $e2GitDir 'commondir')).Trim())))
}
$e2HeadText=[IO.File]::ReadAllText((Join-Path $e2GitDir 'HEAD')).Trim()
if ($e2HeadText -match '^ref: (refs/heads/[A-Za-z0-9_./-]+)$') {
    $e2Ref=$Matches[1]
    if ($e2Ref.Contains('..')) { throw 'Invalid HEAD ref' }
    $e2RefPath=Join-Path $e2Common $e2Ref
    if ([IO.File]::Exists($e2RefPath)) { $e2Head=[IO.File]::ReadAllText($e2RefPath).Trim() }
    else {
        $e2Found=@([IO.File]::ReadAllLines((Join-Path $e2Common 'packed-refs')) | Where-Object { $_ -match ('^[0-9a-f]{40} '+[regex]::Escape($e2Ref)+'$') })
        if ($e2Found.Count -ne 1) { throw 'HEAD ref not uniquely resolved' }
        $e2Head=$e2Found[0].Substring(0,40)
    }
} else { $e2Head=$e2HeadText }
if ($e2Head -notmatch '^[0-9a-f]{40}$' -or $e2Head -ne $e2Approval.driver_commit) { throw 'Approval HEAD mismatch' }
$e2IndexHash=(Get-FileHash -LiteralPath (Join-Path $e2GitDir 'index') -Algorithm SHA256).Hash.ToLowerInvariant()
if ($e2IndexHash -ne $e2Approval.git_index_sha256) { throw 'Approved index fingerprint changed' }
foreach ($e2Property in $e2Manifest.workspace_files.PSObject.Properties) {
    if ((E2-Elapsed) -ge 90) { throw 'Preparation deadline while checking working-tree inputs' }
    if ((Get-FileHash -LiteralPath (Join-Path $e2Root $e2Property.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $e2Property.Value) {
        throw "Fixed working-tree bytes changed: $($e2Property.Name)"
    }
}
if ((Get-FileHash -LiteralPath (Join-Path $e2Here 'STATIC_CHECKS.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    $e2Approval.static_checks_sha256) { throw 'Static evidence fingerprint changed' }
foreach ($e2Inventory in $e2Manifest.namespace_inventories) {
    if ((E2-Elapsed) -ge 90) { throw 'Preparation deadline while checking namespace inventory' }
    $e2Names=@(Get-ChildItem -LiteralPath (Join-Path $e2Root $e2Inventory.relative_directory) -Force |
        Where-Object { $_.Name -notin $e2Inventory.excluded_names } | ForEach-Object { $_.Name } | Sort-Object)
    if (($e2Names -join "`n") -cne (($e2Inventory.names | Sort-Object) -join "`n")) { throw 'Untracked namespace inventory changed' }
}
$e2PrivateBase = Join-Path $env:LOCALAPPDATA 'CodexEvidence'
$e2Run = Join-Path $e2PrivateBase $EvidenceName
if (Test-Path -LiteralPath $e2Run) { throw 'Evidence path already exists; no retry/overwrite' }
[IO.Directory]::CreateDirectory($e2Run) | Out-Null
[IO.File]::Copy([IO.Path]::GetFullPath($ApprovalPath), (Join-Path $e2Run 'approval.json'), $false)
$e2Outer = [ordered]@{ schema='e2-cli-fixed-driver-v1'; outer_t0_utc=$e2T0Utc;
    outer_t0_qpc=$e2T0Qpc; qpc_frequency=$e2Frequency; driver_commit=$e2Head;
    driver_bundle_sha256=$e2Manifest.driver_bundle_sha256; control_launch_requests=1;
    root_job_active_limit=17; root_job_commit_limit_bytes=2415919104;
    controller_private_budget_bytes=268435456; forced_outer_cleanup=$false;
    outer_nonce=([Guid]::NewGuid().ToString('N')+[Guid]::NewGuid().ToString('N'));
    preparation_external_process_requests=0; fixed_workspace_files=@($e2Manifest.workspace_files.PSObject.Properties).Count;
    git_index_sha256=$e2IndexHash;
    status='preparing'; close_errors=@() }
function Save-E2Outer {
    $e2OuterTemp=Join-Path $e2Run ('outer-'+[Guid]::NewGuid().ToString('N')+'.tmp')
    [IO.File]::WriteAllText($e2OuterTemp,
        ($e2Outer | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
    [IO.File]::Move($e2OuterTemp,(Join-Path $e2Run 'outer.json'),$true)
}
Save-E2Outer

$e2Assembly = [Reflection.Emit.AssemblyBuilder]::DefineDynamicAssembly(
    [Reflection.AssemblyName]::new('E2GateInterop'), [Reflection.Emit.AssemblyBuilderAccess]::Run)
$e2Type = $e2Assembly.DefineDynamicModule('E2GateInterop').DefineType('E2Native', 'Public, Sealed, Abstract')
function Add-E2Native([string]$Name, [type]$Return, [type[]]$Arguments) {
    $e2Method = $e2Type.DefinePInvokeMethod($Name, 'kernel32.dll', 'Public, Static, PinvokeImpl',
        [Reflection.CallingConventions]::Standard, $Return, $Arguments,
        [Runtime.InteropServices.CallingConvention]::Winapi, [Runtime.InteropServices.CharSet]::Unicode)
    $e2Ctor = [Runtime.InteropServices.DllImportAttribute].GetConstructor([type[]]@([string]))
    $e2Fields = [Reflection.FieldInfo[]]@([Runtime.InteropServices.DllImportAttribute].GetField('SetLastError'))
    $e2Attribute = [Reflection.Emit.CustomAttributeBuilder]::new($e2Ctor, [object[]]@('kernel32.dll'),
        $e2Fields, [object[]]@($true))
    $e2Method.SetCustomAttribute($e2Attribute)
    $e2Method.SetImplementationFlags([Reflection.MethodImplAttributes]::PreserveSig)
}
Add-E2Native 'CreateJobObjectW' ([IntPtr]) @([IntPtr],[string])
Add-E2Native 'SetInformationJobObject' ([bool]) @([IntPtr],[int],[IntPtr],[uint32])
Add-E2Native 'QueryInformationJobObject' ([bool]) @([IntPtr],[int],[IntPtr],[uint32],[IntPtr])
Add-E2Native 'CreateProcessW' ([bool]) @([string],[Text.StringBuilder],[IntPtr],[IntPtr],[bool],[uint32],[IntPtr],[string],[IntPtr],[IntPtr])
Add-E2Native 'AssignProcessToJobObject' ([bool]) @([IntPtr],[IntPtr])
Add-E2Native 'ResumeThread' ([uint32]) @([IntPtr])
Add-E2Native 'WaitForSingleObject' ([uint32]) @([IntPtr],[uint32])
Add-E2Native 'TerminateJobObject' ([bool]) @([IntPtr],[uint32])
Add-E2Native 'TerminateProcess' ([bool]) @([IntPtr],[uint32])
Add-E2Native 'GetExitCodeProcess' ([bool]) @([IntPtr],[IntPtr])
Add-E2Native 'GetHandleInformation' ([bool]) @([IntPtr],[IntPtr])
Add-E2Native 'OpenProcess' ([IntPtr]) @([uint32],[bool],[uint32])
Add-E2Native 'GetProcessTimes' ([bool]) @([IntPtr],[IntPtr],[IntPtr],[IntPtr],[IntPtr])
Add-E2Native 'QueryFullProcessImageNameW' ([bool]) @([IntPtr],[uint32],[Text.StringBuilder],[IntPtr])
Add-E2Native 'CloseHandle' ([bool]) @([IntPtr])
$e2Native = $e2Type.CreateType()
function E2-Check([bool]$Result, [string]$Label) {
    if (-not $Result) { throw "$Label failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())" }
}
function E2-Quote([string]$Value) {
    $e2Text = [Text.StringBuilder]::new('"')
    $e2Slashes = 0
    foreach ($e2Char in $Value.ToCharArray()) {
        if ($e2Char -eq '\') { $e2Slashes++; continue }
        if ($e2Char -eq '"') { [void]$e2Text.Append(('\' * (2*$e2Slashes+1))) }
        else { [void]$e2Text.Append(('\' * $e2Slashes)) }
        [void]$e2Text.Append($e2Char); $e2Slashes=0
    }
    [void]$e2Text.Append(('\' * (2*$e2Slashes))); [void]$e2Text.Append('"')
    $e2Text.ToString()
}
$e2Job = [IntPtr]::Zero; $e2Process = [IntPtr]::Zero; $e2Thread = [IntPtr]::Zero
$e2Buffers = [Collections.Generic.List[IntPtr]]::new()
$e2Assigned = $false
$e2ControllerObservers=[Collections.Generic.List[object]]::new()
$e2ControllerAcked=$false
try {
    $e2Limits = [Runtime.InteropServices.Marshal]::AllocHGlobal(144); $e2Buffers.Add($e2Limits)
    [Runtime.InteropServices.Marshal]::Copy([byte[]]::new(144),0,$e2Limits,144)
    [Runtime.InteropServices.Marshal]::WriteInt32($e2Limits,16,0x2208)
    [Runtime.InteropServices.Marshal]::WriteInt32($e2Limits,40,17)
    [Runtime.InteropServices.Marshal]::WriteInt64($e2Limits,120,2415919104)
    $e2JobName = 'Local\e2-cli-outer-' + [Guid]::NewGuid().ToString('N')
    $e2Job = $e2Native::CreateJobObjectW([IntPtr]::Zero,$e2JobName)
    $e2CreateError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    E2-Check ($e2Job -ne [IntPtr]::Zero) 'Create outer Job'
    if ($e2CreateError -eq 183) { throw 'Job collision; never take over an existing Job' }
    $e2Outer.root_job_name=$e2JobName
    Save-E2Outer
    E2-Check ($e2Native::SetInformationJobObject($e2Job,9,$e2Limits,144)) 'Set root limits'
    E2-Check ($e2Native::QueryInformationJobObject($e2Job,9,$e2Limits,144,[IntPtr]::Zero)) 'Read root limits'
    if ([Runtime.InteropServices.Marshal]::ReadInt32($e2Limits,16) -ne 0x2208 -or
        [Runtime.InteropServices.Marshal]::ReadInt32($e2Limits,40) -ne 17 -or
        [Runtime.InteropServices.Marshal]::ReadInt64($e2Limits,120) -ne 2415919104) { throw 'Root limit readback mismatch' }
    $e2Si = [Runtime.InteropServices.Marshal]::AllocHGlobal(104); $e2Buffers.Add($e2Si)
    $e2Pi = [Runtime.InteropServices.Marshal]::AllocHGlobal(24); $e2Buffers.Add($e2Pi)
    $e2Accounting = [Runtime.InteropServices.Marshal]::AllocHGlobal(48); $e2Buffers.Add($e2Accounting)
    $e2Exit = [Runtime.InteropServices.Marshal]::AllocHGlobal(4); $e2Buffers.Add($e2Exit)
    $e2PidList = [Runtime.InteropServices.Marshal]::AllocHGlobal(144); $e2Buffers.Add($e2PidList)
    $e2Times = [Runtime.InteropServices.Marshal]::AllocHGlobal(32); $e2Buffers.Add($e2Times)
    [Runtime.InteropServices.Marshal]::Copy([byte[]]::new(104),0,$e2Si,104)
    [Runtime.InteropServices.Marshal]::Copy([byte[]]::new(24),0,$e2Pi,24)
    [Runtime.InteropServices.Marshal]::WriteInt32($e2Si,0,104)
    $e2Python = Join-Path $e2Root '.venv/Scripts/python.exe'
    $e2Tokens = @($e2Python,'-I','-B','-X','utf8',(Join-Path $e2Here 'controller.py'),$e2Run)
    $e2Command = [Text.StringBuilder]::new((($e2Tokens | ForEach-Object { E2-Quote $_ }) -join ' '))
    if ((E2-Elapsed) -ge 90) { throw 'No controller launch after preparation cutoff' }
    E2-Check ($e2Native::CreateProcessW($e2Python,$e2Command,[IntPtr]::Zero,[IntPtr]::Zero,$false,
        0x08000004,[IntPtr]::Zero,$e2Root,$e2Si,$e2Pi)) 'Create suspended controller'
    $e2Process = [Runtime.InteropServices.Marshal]::ReadIntPtr($e2Pi,0)
    $e2Thread = [Runtime.InteropServices.Marshal]::ReadIntPtr($e2Pi,8)
    foreach ($e2Owned in @($e2Job,$e2Process,$e2Thread)) {
        E2-Check ($e2Native::GetHandleInformation($e2Owned,$e2Exit)) 'Outer handle inheritance'
        if (([Runtime.InteropServices.Marshal]::ReadInt32($e2Exit) -band 1) -ne 0) { throw 'Unexpected inherited outer handle' }
    }
    $e2Outer.owner_handles_noninheritable=$true
    $e2Outer.launcher_pid = [Runtime.InteropServices.Marshal]::ReadInt32($e2Pi,16)
    E2-Check ($e2Native::AssignProcessToJobObject($e2Job,$e2Process)) 'Assign outer Job'
    $e2Assigned = $true
    $e2Outer.assigned_before_resume=$true
    $e2Resume = $e2Native::ResumeThread($e2Thread)
    $e2Outer.resume_previous_count=$e2Resume
    if ($e2Resume -ne 1) { throw 'ResumeThread must return exactly 1' }
    $e2Outer.status='controller_running'; Save-E2Outer
    while ($e2Native::WaitForSingleObject($e2Process,20) -eq 258) {
        $e2BootFile = Join-Path $e2Run 'controller.boot.json'
        if ((E2-Elapsed) -ge 660 -or ((E2-Elapsed) -ge 90 -and -not (Test-Path -LiteralPath $e2BootFile))) {
            throw 'Outer watchdog cutoff'
        }
        if (Test-Path -LiteralPath $e2BootFile) {
            $e2Boot=Get-Content -LiteralPath $e2BootFile -Raw | ConvertFrom-Json
            if (-not $e2ControllerAcked) {
                if ($e2Boot.outer_nonce -cne $e2Outer.outer_nonce) { throw 'Controller outer nonce mismatch' }
                E2-Check ($e2Native::QueryInformationJobObject($e2Job,3,$e2PidList,144,[IntPtr]::Zero)) 'Controller complete PID set'
                $e2AssignedCount=[Runtime.InteropServices.Marshal]::ReadInt32($e2PidList,0)
                $e2ListedCount=[Runtime.InteropServices.Marshal]::ReadInt32($e2PidList,4)
                E2-Check ($e2Native::QueryInformationJobObject($e2Job,1,$e2Accounting,48,[IntPtr]::Zero)) 'Controller admission accounting'
                $e2ControllerTotal=[Runtime.InteropServices.Marshal]::ReadInt32($e2Accounting,36)
                if ($e2AssignedCount -ne $e2ListedCount -or $e2ListedCount -lt 1 -or $e2ListedCount -gt 3 -or
                    $e2ControllerTotal -ne $e2ListedCount) { throw 'Controller independent <=3 admission or completeness failed' }
                $e2CfgHome=(@([IO.File]::ReadAllLines((Join-Path $e2Root '.venv/pyvenv.cfg')) | Where-Object { $_.StartsWith('home = ') })[0]).Substring(7)
                $e2Allowed=@([IO.Path]::GetFullPath($e2Python).ToLowerInvariant(),[IO.Path]::GetFullPath((Join-Path $e2CfgHome 'python.exe')).ToLowerInvariant())
                for ($e2I=0;$e2I -lt $e2ListedCount;$e2I++) {
                    $e2MemberPid=[uint32][Runtime.InteropServices.Marshal]::ReadInt64($e2PidList,(8+8*$e2I))
                    $e2Observer=$e2Native::OpenProcess(0x101000,$false,$e2MemberPid)
                    E2-Check ($e2Observer -ne [IntPtr]::Zero) 'Controller observer handle'
                    $e2Identity=[ordered]@{pid=$e2MemberPid;handle=$e2Observer;parent_pid=$null;parent_source='unknown internal edge'}
                    $e2ControllerObservers.Add($e2Identity)
                    E2-Check ($e2Native::GetHandleInformation($e2Observer,$e2Exit)) 'Controller observer inheritance'
                    if (([Runtime.InteropServices.Marshal]::ReadInt32($e2Exit) -band 1) -ne 0) { throw 'Inherited observer' }
                    E2-Check ($e2Native::GetProcessTimes($e2Observer,$e2Times,[IntPtr]::Add($e2Times,8),[IntPtr]::Add($e2Times,16),[IntPtr]::Add($e2Times,24))) 'Controller creation time'
                    $e2Identity.creation_filetime=[Runtime.InteropServices.Marshal]::ReadInt64($e2Times,0)
                    $e2Image=[Text.StringBuilder]::new(32768)
                    [Runtime.InteropServices.Marshal]::WriteInt32($e2Exit,32768)
                    E2-Check ($e2Native::QueryFullProcessImageNameW($e2Observer,0,$e2Image,$e2Exit)) 'Controller image'
                    $e2Identity.image=$e2Image.ToString()
                    if ($e2Identity.image.ToLowerInvariant() -notin $e2Allowed) { throw 'Unknown controller image' }
                    if ($e2MemberPid -eq $e2Outer.launcher_pid) { $e2Identity.parent_pid=$PID; $e2Identity.parent_source='CreateProcess caller' }
                    if ($e2MemberPid -eq $e2Boot.pid) {
                        if ($e2Identity.creation_filetime -ne $e2Boot.creation_filetime) { throw 'Controller PID reused' }
                        $e2Identity.parent_pid=$e2Boot.parent_pid; $e2Identity.parent_source='controller self-report, creation bound'
                    }
                }
                if ($e2Boot.pid -notin @($e2ControllerObservers | ForEach-Object {$_.pid}) -or
                    $e2Outer.launcher_pid -notin @($e2ControllerObservers | ForEach-Object {$_.pid})) { throw 'Known controller identities absent' }
                $e2Outer.controller_os_count=$e2ControllerTotal
                $e2Outer.controller_identity=@($e2ControllerObservers | ForEach-Object { @{pid=$_.pid;parent_pid=$_.parent_pid;parent_source=$_.parent_source;creation_filetime=$_.creation_filetime;image=$_.image;handle_inheritable=$false} })
                Save-E2Outer
                $e2Ack=@{outer_nonce=$e2Outer.outer_nonce;controller_pid=$e2Boot.pid;controller_os_count=$e2ControllerTotal;complete_pids=@($e2ControllerObservers | ForEach-Object {$_.pid});driver_bundle_sha256=$e2Manifest.driver_bundle_sha256}
                $e2AckTemp=Join-Path $e2Run 'controller.ack.tmp'
                [IO.File]::WriteAllText($e2AckTemp,($e2Ack|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
                [IO.File]::Move($e2AckTemp,(Join-Path $e2Run 'controller.ack.private.json'))
                $e2ControllerAcked=$true
            }
            $e2Actual=Get-Process -Id $e2Boot.pid -ErrorAction SilentlyContinue
            if ($e2Actual -and $e2Actual.StartTime.ToUniversalTime().ToFileTimeUtc() -eq $e2Boot.creation_filetime -and
                $e2Actual.PrivateMemorySize64 -gt 268435456) { throw 'Controller private memory budget exceeded' }
        }
    }
    E2-Check ($e2Native::GetExitCodeProcess($e2Process,$e2Exit)) 'Controller exit code'
    $e2Outer.launcher_exit_dword=[BitConverter]::ToUInt32([BitConverter]::GetBytes([Runtime.InteropServices.Marshal]::ReadInt32($e2Exit)),0)
    E2-Check ($e2Native::QueryInformationJobObject($e2Job,1,$e2Accounting,48,[IntPtr]::Zero)) 'Root accounting'
    $e2Outer.root_cumulative_OS_processes=[Runtime.InteropServices.Marshal]::ReadInt32($e2Accounting,36)
    $e2Outer.root_active_after_controller=[Runtime.InteropServices.Marshal]::ReadInt32($e2Accounting,40)
    if ($e2Outer.root_active_after_controller -ne 0) { throw 'Launcher exited with live root Job descendants' }
    if (-not $e2ControllerAcked) { throw 'Controller never completed independent admission' }
    $e2Final=Get-Content -LiteralPath (Join-Path $e2Run 'final.accounting.json') -Raw | ConvertFrom-Json
    if (-not $e2Final.complete -or $e2Final.state -ne 'matrix_passed_pending_evidence_review' -or
        $e2Final.case_records.Count -ne 15 -or
        $e2Final.controller_os_count -ne $e2Outer.controller_os_count -or
        $e2Final.case_OS_total -gt 123 -or $e2Outer.root_cumulative_OS_processes -gt 126 -or
        $e2Outer.root_cumulative_OS_processes -ne ($e2Final.case_OS_total+$e2Outer.controller_os_count)) {
        throw 'Whole-window OS accounting does not reconcile'
    }
    $e2Outer.whole_OS_accounting_reconciled=$true
    $e2Outer.status='controller_ended'
} catch {
    $e2CatchDeadline=[Math]::Min(670,(E2-Elapsed)+10)
    $e2Outer.error=$_.Exception.Message; $e2Outer.status='stopped'
    if ($e2Job -ne [IntPtr]::Zero -and $e2CreateError -ne 183) {
        $e2Outer.forced_outer_cleanup=$true
        $e2Outer.root_terminate_success=$e2Native::TerminateJobObject($e2Job,[uint32]3758096385)
    }
    if ($e2Process -ne [IntPtr]::Zero -and -not $e2Assigned) {
        $e2Outer.unassigned_launcher_terminate=$e2Native::TerminateProcess($e2Process,[uint32]3758096385)
    }
    if ($e2Process -ne [IntPtr]::Zero) {
        $e2Remaining=[Math]::Max(0,($e2CatchDeadline-(E2-Elapsed))*1000)
        $e2Outer.cleanup_launcher_wait=$e2Native::WaitForSingleObject($e2Process,[uint32]$e2Remaining)
    }
    if ($e2Assigned -and $e2Accounting -ne [IntPtr]::Zero) {
        do {
            $e2QueryOk=$e2Native::QueryInformationJobObject($e2Job,1,$e2Accounting,48,[IntPtr]::Zero)
            $e2Outer.cleanup_root_query_success=$e2QueryOk
            if (-not $e2QueryOk) { break }
            $e2Outer.root_active_after_cleanup=[Runtime.InteropServices.Marshal]::ReadInt32($e2Accounting,40)
            $e2Outer.root_cumulative_OS_processes=[Runtime.InteropServices.Marshal]::ReadInt32($e2Accounting,36)
            if ($e2Outer.root_active_after_cleanup -eq 0) { break }
            Start-Sleep -Milliseconds 5
        } while ((E2-Elapsed) -lt $e2CatchDeadline)
    }
} finally {
    $e2Outer.controller_exit_observations=@()
    foreach ($e2Identity in $e2ControllerObservers) {
        $e2Exited=$e2Native::WaitForSingleObject($e2Identity.handle,0) -eq 0
        $e2ExitOk=$e2Native::GetExitCodeProcess($e2Identity.handle,$e2Exit)
        $e2RawCode=$null
        if ($e2ExitOk) { $e2RawCode=[BitConverter]::ToUInt32([BitConverter]::GetBytes([Runtime.InteropServices.Marshal]::ReadInt32($e2Exit)),0) }
        $e2Outer.controller_exit_observations+=@{pid=$e2Identity.pid;creation_filetime=$e2Identity.creation_filetime;signaled=$e2Exited;raw_exit_dword=$e2RawCode}
        if (-not $e2Exited -or -not $e2ExitOk) { $e2Outer.status='controller_exit_incomplete' }
        elseif ($e2RawCode -ne 0) { $e2Outer.status='controller_exit_failed' }
        if (-not $e2Native::CloseHandle($e2Identity.handle)) { $e2Outer.close_errors+=[Runtime.InteropServices.Marshal]::GetLastWin32Error() }
    }
    foreach ($e2Handle in @($e2Thread,$e2Process,$e2Job)) {
        if ($e2Handle -ne [IntPtr]::Zero -and -not $e2Native::CloseHandle($e2Handle)) {
            $e2Outer.close_errors += [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        }
    }
    foreach ($e2Buffer in $e2Buffers) { [Runtime.InteropServices.Marshal]::FreeHGlobal($e2Buffer) }
    $e2Outer.end_utc=[DateTimeOffset]::UtcNow.ToString('o')
    $e2Outer.end_qpc=[Diagnostics.Stopwatch]::GetTimestamp()
    $e2Outer.wall_seconds=($e2Outer.end_qpc-$e2T0Qpc)/$e2Frequency
    Save-E2Outer
}
$e2Outer | ConvertTo-Json -Depth 12
if ($e2Outer.status -ne 'controller_ended' -or $e2Outer.launcher_exit_dword -ne 0 -or $e2Outer.close_errors.Count) { exit 1 }
