[CmdletBinding(PositionalBinding=$false)]
param(
    [string]$Mode,
    [string]$OutputDirectory
)

# STATIC PREPARATION ONLY: this file has never been executed.
# An explicit future approval and an external deadline/termination owner are required.
# No default mode, S path, native invocation, process launch, or retry is provided.
$ErrorActionPreference = 'Stop'
if ($Mode -cne 'Metadata') { throw 'Explicit -Mode Metadata is required; no other mode exists' }
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { throw 'A new output directory is required' }
$mOutput = [IO.Path]::GetFullPath($OutputDirectory)
if ([IO.Directory]::Exists($mOutput) -or [IO.File]::Exists($mOutput)) {
    throw 'Output path already exists; no overwrite or retry'
}
[void][IO.Directory]::CreateDirectory($mOutput)
$mStartUtc = [DateTimeOffset]::UtcNow.ToString('o')
$mStartQpc = [Diagnostics.Stopwatch]::GetTimestamp()
$mFrequency = [Diagnostics.Stopwatch]::Frequency

# Independent, reviewable expectations, transcribed from the fixed 6f source.
# These rows do NOT drive Add-E2Native or provide any observed values.
$mSignatureRows = @(
    'CreateJobObjectW|System.IntPtr|System.IntPtr,System.String'
    'SetInformationJobObject|System.Boolean|System.IntPtr,System.Int32,System.IntPtr,System.UInt32'
    'QueryInformationJobObject|System.Boolean|System.IntPtr,System.Int32,System.IntPtr,System.UInt32,System.IntPtr'
    'CreateProcessW|System.Boolean|System.String,System.Text.StringBuilder,System.IntPtr,System.IntPtr,System.Boolean,System.UInt32,System.IntPtr,System.String,System.IntPtr,System.IntPtr'
    'AssignProcessToJobObject|System.Boolean|System.IntPtr,System.IntPtr'
    'ResumeThread|System.UInt32|System.IntPtr'
    'WaitForSingleObject|System.UInt32|System.IntPtr,System.UInt32'
    'TerminateJobObject|System.Boolean|System.IntPtr,System.UInt32'
    'TerminateProcess|System.Boolean|System.IntPtr,System.UInt32'
    'GetExitCodeProcess|System.Boolean|System.IntPtr,System.IntPtr'
    'GetHandleInformation|System.Boolean|System.IntPtr,System.IntPtr'
    'OpenProcess|System.IntPtr|System.UInt32,System.Boolean,System.UInt32'
    'GetProcessTimes|System.Boolean|System.IntPtr,System.IntPtr,System.IntPtr,System.IntPtr,System.IntPtr'
    'QueryFullProcessImageNameW|System.Boolean|System.IntPtr,System.UInt32,System.Text.StringBuilder,System.IntPtr'
    'CloseHandle|System.Boolean|System.IntPtr'
)
$mCapturedNames = @('CreateJobObjectW', 'QueryInformationJobObject', 'CreateProcessW')
$mExpected = @($mSignatureRows | ForEach-Object {
    $parts = $_.Split('|')
    [ordered]@{ name=$parts[0]; return_type=$parts[1]; parameter_types=@($parts[2].Split(','));
        method_attributes=8214; implementation_flags=128; calling_convention=1;
        dll_import=[ordered]@{ library='kernel32.dll'; EntryPoint=$parts[0]; CharSet='Unicode';
            CallingConvention='Winapi'; SetLastError=$true; ExactSpelling=$true; PreserveSig=$true } }
})
$mReport = [ordered]@{
    schema='e2-metadata-only-v1'; mode=$Mode;
    source_commit='6f91055d37bd94d4d0b9f7789ccb36baf0d44f88';
    source_path='research/a/review/e2_cli_fix_validation_20260924/launch_once.ps1';
    script_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();
    script_t0_utc=$mStartUtc; script_t0_qpc=$mStartQpc; qpc_frequency=$mFrequency;
    external_t0_and_control_os_count='not_observed_by_this_script';
    status='collecting'; first_error=$null; expected=$mExpected;
    expected_captured_names=$mCapturedNames;
    actual_environment=$null; actual_declared_method_names=@(); actual_native=@(); actual_wrappers=@();
    checks=@(); gaps=@(); type_generation_attempted=$false; generated_type_count=$null;
    actual_type=$null;
    declared_native_invocation_requests=0; child_process_launch_requests=0;
    memory_and_hard_deadline_enforcement='external responsibility; not implemented here'
}
$mChecks = [Collections.Generic.List[object]]::new()
$mGaps = [Collections.Generic.List[object]]::new()
$mNativeRecords = [Collections.Generic.List[object]]::new()
$mWrapperRecords = [Collections.Generic.List[object]]::new()

function Add-MCheck([string]$Name, $Expected, $Actual) {
    # Serialize values separately; neither side is filled from the other.
    $expectedText = ConvertTo-Json -InputObject $Expected -Depth 8 -Compress
    $actualText = ConvertTo-Json -InputObject $Actual -Depth 8 -Compress
    $mChecks.Add([ordered]@{ name=$Name; expected=$Expected; actual=$Actual;
        matches=($expectedText -ceq $actualText) })
}
function Get-MMethodSignature([Reflection.MethodInfo]$Method) {
    $parameters = @($Method.GetParameters() | ForEach-Object { $_.ParameterType.FullName })
    return ($Method.DeclaringType.FullName+'::'+$Method.Name+'('+($parameters -join ',')+')->'+$Method.ReturnType.FullName)
}
function Read-MInstructions([Reflection.MethodInfo]$Method, [byte[]]$Bytes) {
    # Deliberately bounded to the 6f wrapper vocabulary. Unsupported IL is a gap,
    # never an invitation to execute/JIT the method or substitute another probe.
    $position=0
    while ($position -lt $Bytes.Length) {
        $offset=$position; $code=[int]$Bytes[$position]; $position++
        $operand=$null; $token=$null; $targetAssembly=$null; $scope=$null; $width=0; $kind='none'
        $opcode=$null
        switch ($code) {
            2  { $opcode='ldarg'; $operand=0 }
            3  { $opcode='ldarg'; $operand=1 }
            4  { $opcode='ldarg'; $operand=2 }
            5  { $opcode='ldarg'; $operand=3 }
            6  { $opcode='ldloc'; $operand=0 }
            7  { $opcode='ldloc'; $operand=1 }
            8  { $opcode='ldloc'; $operand=2 }
            9  { $opcode='ldloc'; $operand=3 }
            10 { $opcode='stloc'; $operand=0 }
            11 { $opcode='stloc'; $operand=1 }
            12 { $opcode='stloc'; $operand=2 }
            13 { $opcode='stloc'; $operand=3 }
            14 { $opcode='ldarg'; $width=1; $kind='index' }
            17 { $opcode='ldloc'; $width=1; $kind='index' }
            19 { $opcode='stloc'; $width=1; $kind='index' }
            22 { $opcode='ldc.i4'; $operand=0 }
            23 { $opcode='ldc.i4'; $operand=1 }
            40 { $opcode='call'; $width=4; $kind='method' }
            42 { $opcode='ret' }
            116 { $opcode='castclass'; $width=4; $kind='type' }
            129 { $opcode='stobj'; $width=4; $kind='type' }
            143 { $opcode='ldelema'; $width=4; $kind='type' }
            154 { $opcode='ldelem.ref' }
            254 {
                if ($position -ge $Bytes.Length) { throw "Truncated two-byte opcode at $offset" }
                $second=[int]$Bytes[$position]; $position++
                switch ($second) {
                    9 { $opcode='ldarg' }
                    12 { $opcode='ldloc' }
                    14 { $opcode='stloc' }
                    default { throw "Unsupported two-byte opcode at $offset" }
                }
                $width=2; $kind='index'
            }
            default { throw "Unsupported opcode $code at $offset" }
        }
        if ($position+$width -gt $Bytes.Length) { throw "Truncated operand at $offset" }
        if ($kind -eq 'index') {
            if ($width -eq 1) { $operand=[int]$Bytes[$position] }
            else { $operand=[int][BitConverter]::ToUInt16($Bytes,$position) }
        } elseif ($kind -eq 'type') {
            $token=[BitConverter]::ToInt32($Bytes,$position)
            $resolved=$Method.Module.ResolveType($token)
            $operand=$resolved.FullName; $targetAssembly=$resolved.Assembly.FullName
            if ($resolved.Assembly -ne [int].Assembly) { throw "Unexpected type-token assembly at $offset" }
        } elseif ($kind -eq 'method') {
            $token=[BitConverter]::ToInt32($Bytes,$position)
            $resolved=$Method.Module.ResolveMethod($token)
            $operand=Get-MMethodSignature $resolved
            $targetAssembly=$resolved.DeclaringType.Assembly.FullName
            if ($resolved.DeclaringType -eq $e2Native) { $scope='emitted_type' }
            elseif ($resolved.DeclaringType -eq [Runtime.InteropServices.Marshal]) { $scope='runtime_marshal' }
            else { $scope='unexpected' }
            $operand=$operand+'#'+$scope
        }
        $position+=$width
        $semantic=$opcode
        if ($null -ne $operand) { $semantic+=':'+([string]$operand) }
        [ordered]@{ offset=$offset; opcode=$opcode; operand=$operand; token=$token;
            target_assembly=$targetAssembly; semantic=$semantic }
    }
}
function Get-MExpectedInstructions($Signature) {
    # Independent semantic specification; never inspects MethodBuilder or actual IL.
    $arity=$Signature.parameter_types.Count; $result=$Signature.return_type
    @("ldarg:$arity", 'ldc.i4:0', 'ldelem.ref', "castclass:${result}[]", 'ldc.i4:0',
        "ldelema:$result", 'stloc:2', "ldarg:$arity", 'ldc.i4:1', 'ldelem.ref',
        'castclass:System.Int32[]', 'ldc.i4:0', 'ldelema:System.Int32', 'stloc:3')
    for ($index=0; $index -lt $arity; $index++) { "ldarg:$index" }
    'call:E2Native::'+$Signature.name+'('+($Signature.parameter_types -join ',')+')->'+$result+'#emitted_type'
    @('stloc:0', 'call:System.Runtime.InteropServices.Marshal::GetLastPInvokeError()->System.Int32#runtime_marshal',
        'stloc:1', 'ldloc:2', 'ldloc:0', "stobj:$result", 'ldloc:3', 'ldloc:1', 'stobj:System.Int32', 'ret')
}

try {
    $mReport.actual_environment=[ordered]@{
        powershell_version=$PSVersionTable.PSVersion.ToString(); powershell_edition=$PSVersionTable.PSEdition;
        clr_version=[Environment]::Version.ToString(); framework=[Runtime.InteropServices.RuntimeInformation]::FrameworkDescription;
        pointer_size=[IntPtr]::Size; process_architecture=[Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString();
        os_architecture=[Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString();
        os_platform=[Environment]::OSVersion.Platform.ToString(); language_mode=$ExecutionContext.SessionState.LanguageMode.ToString()
    }
    Add-MCheck 'environment.pointer_size' 8 $mReport.actual_environment.pointer_size
    Add-MCheck 'environment.process_architecture' 'X64' $mReport.actual_environment.process_architecture
    Add-MCheck 'environment.os_platform' 'Win32NT' $mReport.actual_environment.os_platform
    if (@($mChecks | Where-Object { -not $_.matches }).Count -ne 0) {
        throw 'Environment mismatch; no type generation attempted'
    }

    $mReport.type_generation_attempted=$true
# BEGIN EXACT 6f DECLARATION/TYPES BLOCK -- byte-for-byte excerpt, lines 95-177.
$e2Assembly = [Reflection.Emit.AssemblyBuilder]::DefineDynamicAssembly(
    [Reflection.AssemblyName]::new('E2GateInterop'), [Reflection.Emit.AssemblyBuilderAccess]::Run)
$e2Type = $e2Assembly.DefineDynamicModule('E2GateInterop').DefineType('E2Native', 'Public, Sealed, Abstract')
function Add-E2Native([string]$Name, [type]$Return, [type[]]$Arguments, [switch]$CaptureError) {
    # One P/Invoke metadata path: DefineMethod plus one fully specified DllImport.
    # Do not also call DefinePInvokeMethod or rely on attribute/map merging.
    $e2Method = $e2Type.DefineMethod($Name, [Reflection.MethodAttributes]'Public, Static, PinvokeImpl',
        [Reflection.CallingConventions]::Standard, $Return, $Arguments)
    $e2Ctor = [Runtime.InteropServices.DllImportAttribute].GetConstructor([type[]]@([string]))
    $e2Fields = [Reflection.FieldInfo[]]@(
        [Runtime.InteropServices.DllImportAttribute].GetField('EntryPoint'),
        [Runtime.InteropServices.DllImportAttribute].GetField('CharSet'),
        [Runtime.InteropServices.DllImportAttribute].GetField('CallingConvention'),
        [Runtime.InteropServices.DllImportAttribute].GetField('SetLastError'),
        [Runtime.InteropServices.DllImportAttribute].GetField('ExactSpelling'),
        [Runtime.InteropServices.DllImportAttribute].GetField('PreserveSig'))
    $e2Attribute = [Reflection.Emit.CustomAttributeBuilder]::new($e2Ctor, [object[]]@('kernel32.dll'),
        $e2Fields, [object[]]@($Name, [Runtime.InteropServices.CharSet]::Unicode,
            [Runtime.InteropServices.CallingConvention]::Winapi, $true, $true, $true))
    $e2Method.SetCustomAttribute($e2Attribute)
    if ($CaptureError) {
        # Caller owns object[]{nativeResult[1], intError[1]} before the call.
        # Validate fresh typed array slots before creating any native resource.
        # Native call -> store result -> GetLastPInvokeError, with no PowerShell
        # binding, logging, allocation or other native call between them.
        $e2CaptureArguments = [type[]](@($Arguments) + @([object[]]))
        $e2Capture = $e2Type.DefineMethod(($Name+'Captured'), [Reflection.MethodAttributes]'Public, Static',
            [Reflection.CallingConventions]::Standard, [void], $e2CaptureArguments)
        $e2Il = $e2Capture.GetILGenerator()
        $e2ResultLocal = $e2Il.DeclareLocal($Return)
        $e2ErrorLocal = $e2Il.DeclareLocal([int])
        $e2ResultSlot = $e2Il.DeclareLocal($Return.MakeByRefType())
        $e2ErrorSlot = $e2Il.DeclareLocal([int].MakeByRefType())
        $e2GetError = [Runtime.InteropServices.Marshal].GetMethod('GetLastPInvokeError', [type[]]@())
        if ($null -eq $e2GetError) { throw 'Required managed P/Invoke error getter unavailable' }
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldarg, [int16]$Arguments.Count)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldc_I4_0)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldelem_Ref)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Castclass, $Return.MakeArrayType())
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldc_I4_0)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldelema, $Return)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Stloc, $e2ResultSlot)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldarg, [int16]$Arguments.Count)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldc_I4_1)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldelem_Ref)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Castclass, [int[]])
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldc_I4_0)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldelema, [int])
        $e2Il.Emit([Reflection.Emit.OpCodes]::Stloc, $e2ErrorSlot)
        for ($e2Arg=0; $e2Arg -lt $Arguments.Count; $e2Arg++) {
            $e2Il.Emit([Reflection.Emit.OpCodes]::Ldarg, [int16]$e2Arg)
        }
        $e2Il.Emit([Reflection.Emit.OpCodes]::Call, $e2Method)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Stloc, $e2ResultLocal)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Call, $e2GetError)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Stloc, $e2ErrorLocal)
        # Only stores through validated managed references follow capture.
        # No Newarr/Box/Unbox, logging, or returned-array marshalling here.
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldloc, $e2ResultSlot)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldloc, $e2ResultLocal)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Stobj, $Return)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldloc, $e2ErrorSlot)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ldloc, $e2ErrorLocal)
        $e2Il.Emit([Reflection.Emit.OpCodes]::Stobj, [int])
        $e2Il.Emit([Reflection.Emit.OpCodes]::Ret)
    }
}
Add-E2Native 'CreateJobObjectW' ([IntPtr]) @([IntPtr],[string]) -CaptureError
Add-E2Native 'SetInformationJobObject' ([bool]) @([IntPtr],[int],[IntPtr],[uint32])
Add-E2Native 'QueryInformationJobObject' ([bool]) @([IntPtr],[int],[IntPtr],[uint32],[IntPtr]) -CaptureError
Add-E2Native 'CreateProcessW' ([bool]) @([string],[Text.StringBuilder],[IntPtr],[IntPtr],[bool],[uint32],[IntPtr],[string],[IntPtr],[IntPtr]) -CaptureError
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
# END EXACT 6f DECLARATION/TYPES BLOCK

    $mReport.generated_type_count=1
    $mReport.actual_type=[ordered]@{ full_name=$e2Native.FullName;
        assembly=$e2Native.Assembly.FullName; assembly_simple_name=$e2Native.Assembly.GetName().Name;
        module=$e2Native.Module.Name; module_scope=$e2Native.Module.ScopeName; is_dynamic=$e2Native.Assembly.IsDynamic }
    Add-MCheck 'type.full_name' 'E2Native' $mReport.actual_type.full_name
    Add-MCheck 'type.assembly_simple_name' 'E2GateInterop' $mReport.actual_type.assembly_simple_name
    Add-MCheck 'type.is_dynamic' $true $mReport.actual_type.is_dynamic
    $binding=[Reflection.BindingFlags]'Public, NonPublic, Static, Instance, DeclaredOnly'
    $mReport.actual_declared_method_names=@($e2Native.GetMethods($binding) | ForEach-Object { $_.Name } | Sort-Object)
    $expectedNames=@(@($mExpected | ForEach-Object { $_.name }) + @($mCapturedNames | ForEach-Object { $_+'Captured' }) | Sort-Object)
    Add-MCheck 'declared_method_names' $expectedNames $mReport.actual_declared_method_names
    foreach ($expected in $mExpected) {
        $record=[ordered]@{ name=$expected.name; metadata=$null; gap=$null }
        $mNativeRecords.Add($record)
        try {
            $method=$e2Native.GetMethod($expected.name,$binding)
            if ($null -eq $method) { throw 'MethodInfo missing' }
            $record.metadata=[ordered]@{
                name=$method.Name; return_type=$method.ReturnType.FullName;
                parameter_types=@($method.GetParameters() | ForEach-Object { $_.ParameterType.FullName });
                method_attributes=[int]$method.Attributes; implementation_flags=[int]$method.GetMethodImplementationFlags();
                calling_convention=[int]$method.CallingConvention; dll_import=$null
            }
            $imports=@($method.GetCustomAttributes([Runtime.InteropServices.DllImportAttribute],$false))
            Add-MCheck ($expected.name+'.dll_import_count') 1 $imports.Count
            if ($imports.Count -ne 1) { throw 'Expected exactly one actual DllImportAttribute' }
            $import=$imports[0]
            $record.metadata.dll_import=[ordered]@{
                library=$import.Value; EntryPoint=$import.EntryPoint; CharSet=$import.CharSet.ToString();
                CallingConvention=$import.CallingConvention.ToString(); SetLastError=$import.SetLastError;
                ExactSpelling=$import.ExactSpelling; PreserveSig=$import.PreserveSig
            }
            Add-MCheck ($expected.name+'.metadata') $expected $record.metadata
        } catch {
            $record.gap=[ordered]@{ exception_type=$_.Exception.GetType().FullName; message=$_.Exception.Message }
            if ($null -eq $mReport.first_error) { $mReport.first_error=$record.gap }
            $mGaps.Add([ordered]@{ stage=$expected.name; detail=$record.gap })
        }
    }
    foreach ($name in $mCapturedNames) {
        $record=[ordered]@{ name=($name+'Captured'); signature=$null; locals=$null;
            init_locals=$null; exception_clause_count=$null; max_stack=$null;
            raw_il_base64=$null; instructions=@(); expected_instructions=@(); gap=$null }
        $mWrapperRecords.Add($record)
        try {
            $spec=@($mExpected | Where-Object { $_.name -ceq $name })[0]
            $method=$e2Native.GetMethod(($name+'Captured'),$binding)
            if ($null -eq $method) { throw 'Captured MethodInfo missing' }
            $record.signature=[ordered]@{ return_type=$method.ReturnType.FullName;
                parameter_types=@($method.GetParameters() | ForEach-Object { $_.ParameterType.FullName });
                method_attributes=[int]$method.Attributes; implementation_flags=[int]$method.GetMethodImplementationFlags();
                calling_convention=[int]$method.CallingConvention }
            $expectedSignature=[ordered]@{ return_type='System.Void'; parameter_types=@($spec.parameter_types)+@('System.Object[]');
                method_attributes=22; implementation_flags=0; calling_convention=1 }
            Add-MCheck ($name+'.captured_signature') $expectedSignature $record.signature
            $body=$method.GetMethodBody()
            if ($null -eq $body) { throw 'MethodBody unavailable; no fallback probe' }
            $record.locals=@($body.LocalVariables | ForEach-Object {
                [ordered]@{ index=$_.LocalIndex; type=$_.LocalType.FullName; pinned=$_.IsPinned }
            })
            $expectedLocals=@(
                [ordered]@{ index=0; type=$spec.return_type; pinned=$false },
                [ordered]@{ index=1; type='System.Int32'; pinned=$false },
                [ordered]@{ index=2; type=($spec.return_type+'&'); pinned=$false },
                [ordered]@{ index=3; type='System.Int32&'; pinned=$false })
            Add-MCheck ($name+'.locals') $expectedLocals $record.locals
            $record.init_locals=$body.InitLocals; $record.exception_clause_count=$body.ExceptionHandlingClauses.Count
            $record.max_stack=$body.MaxStackSize
            Add-MCheck ($name+'.init_locals') $true $record.init_locals
            Add-MCheck ($name+'.exception_clauses') 0 $record.exception_clause_count
            $bytes=$body.GetILAsByteArray()
            if ($null -eq $bytes -or $bytes.Length -eq 0) { throw 'IL bytes unavailable; no fallback probe' }
            $record.raw_il_base64=[Convert]::ToBase64String($bytes)
            $record.expected_instructions=@(Get-MExpectedInstructions $spec)
            $record.instructions=@(Read-MInstructions $method $bytes)
            $actualInstructions=@($record.instructions | ForEach-Object { $_.semantic })
            Add-MCheck ($name+'.instruction_sequence') $record.expected_instructions $actualInstructions
        } catch {
            $record.gap=[ordered]@{ exception_type=$_.Exception.GetType().FullName; message=$_.Exception.Message }
            if ($null -eq $mReport.first_error) { $mReport.first_error=$record.gap }
            $mGaps.Add([ordered]@{ stage=($name+'Captured'); detail=$record.gap })
        }
    }
    if ($mGaps.Count -gt 0) { $mReport.status='gap' }
    elseif (@($mChecks | Where-Object { -not $_.matches }).Count -gt 0) { $mReport.status='mismatch' }
    else { $mReport.status='metadata_matches_expected_only' }
} catch {
    $mReport.status='gap'
    $failure=[ordered]@{ exception_type=$_.Exception.GetType().FullName; message=$_.Exception.Message }
    if ($null -eq $mReport.first_error) { $mReport.first_error=$failure }
    $mGaps.Add([ordered]@{ stage='generation_or_collection'; detail=$failure })
} finally {
    $mReport.actual_native=@($mNativeRecords.ToArray()); $mReport.actual_wrappers=@($mWrapperRecords.ToArray())
    $mReport.checks=@($mChecks.ToArray()); $mReport.gaps=@($mGaps.ToArray())
    $mReport.collection_end_utc=[DateTimeOffset]::UtcNow.ToString('o')
    $mReport.collection_end_qpc=[Diagnostics.Stopwatch]::GetTimestamp()
    $mReport.collection_seconds=($mReport.collection_end_qpc-$mStartQpc)/$mFrequency
    # Script timing excludes host startup and the following final write/exit.
    # It is evidence, not enforcement of the proposed 30-second outer budget.
    $json=$mReport | ConvertTo-Json -Depth 16
    $utf8=[Text.UTF8Encoding]::new($false)
    $payload=$utf8.GetBytes($json)
    if ($payload.Length -gt 1048576) {
        $mReport.status='gap'
        $json=[ordered]@{ schema='e2-metadata-only-v1'; mode=$Mode; status='gap';
            error='Evidence exceeds 1 MiB; full observations were not saved';
            unsaved_bytes=$payload.Length; script_sha256=$mReport.script_sha256;
            script_t0_utc=$mStartUtc; script_t0_qpc=$mStartQpc; qpc_frequency=$mFrequency } | ConvertTo-Json
        $payload=$utf8.GetBytes($json)
    }
    # CreateNew forbids replacing an existing metadata.json, including a race.
    $stream=[IO.File]::Open((Join-Path $mOutput 'metadata.json'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $stream.Write($payload,0,$payload.Length) } finally { $stream.Dispose() }
}
if ($mReport.status -cne 'metadata_matches_expected_only') { exit 2 }
exit 0
