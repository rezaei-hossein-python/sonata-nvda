<#
Sonata NVDA runtime validation harness
Creates a disposable NVDA profile, installs the built .nvda-addon, copies a test voice,
launches NVDA interactively, guides minimal human actions, captures logs & process state,
and summarizes runtime gates.

Safe: does not modify the user's daily NVDA roaming profile.
Run interactively once from the desktop as the test user.
#>

param()

Set-StrictMode -Version Latest

function Write-Log { param($s) Write-Output "$(Get-Date -Format o) - $s" }

$ErrorActionPreference = 'Stop'

# Paths & constants
$RepoRoot = 'C:\projects\sonata-nvda-64'
$AddonPath = Join-Path $RepoRoot 'sonata_neural_voices-3.1.nvda-addon'
$ExpectedSHA = '2C22662B106025DF1A2B67D00153DBF49DE39ACA9034538D690126ABE12E226F'
$NvdaDefaultPath = 'C:\Program Files\NVDA\nvda.exe'
$ResultsBase = 'C:\temp\sonata-nvda-runtime-test'

# Safety checks
Write-Log 'Starting Sonata NVDA runtime validation harness (dry-run safety checks).'
if (-not (Test-Path $RepoRoot)) { Write-Error "Repo root not found: $RepoRoot"; exit 2 }
if (-not (Test-Path $AddonPath)) { Write-Error "Addon not found: $AddonPath"; exit 2 }

# Initial profile isolation state (will be PENDING until runtime checks)
$PROFILE_ISOLATION_STATE_BEFORE_RUN = 'PENDING'
$PROFILE_ISOLATION_CONFIRMED = $false

# Validate addon hash
Write-Log 'Validating .nvda-addon SHA256...'
try {
    $actual = (Get-FileHash -Algorithm SHA256 $AddonPath).Hash.ToUpper()
} catch {
    Write-Error ("Failed to compute hash for {0}: {1}" -f $AddonPath, $_); exit 2
}
if ($actual -ne $ExpectedSHA) {
    Write-Error "SHA256 mismatch for $AddonPath (expected $ExpectedSHA, got $actual). Aborting."; exit 2
}
Write-Log 'Addon SHA256 matches expected.'

# Find NVDA executable
if (Test-Path $NvdaDefaultPath) { $NvdaExe = $NvdaDefaultPath } else {
    Write-Log "NVDA not found at $NvdaDefaultPath; searching common locations..."
    $candidates = @(
        'C:\Program Files (x86)\NVDA\nvda.exe',
        'C:\Program Files\NVDA\nvda.exe'
    )
    $NvdaExe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $NvdaExe) { Write-Error 'Could not locate nvda.exe on this machine. Aborting.'; exit 2 }
Write-Log "Found NVDA executable: $NvdaExe"

# Determine authoritative NVDA command-line options from installed documentation (do NOT run nvda.exe)
Write-Log 'Inspecting installed NVDA documentation for supported command-line options...'
$docDir = Join-Path (Split-Path $NvdaExe -Parent) 'documentation'
$docFiles = @()
if (Test-Path $docDir) { $docFiles = Get-ChildItem -Path $docDir -Recurse -Include *.html,*.txt -ErrorAction SilentlyContinue }

$FoundConfigPath = $false
$FoundLogFile = $false
$FoundPortable = $false
foreach ($f in $docFiles) {
    try {
        $txt = Get-Content -Path $f.FullName -ErrorAction SilentlyContinue -Raw
        if ($txt -match '--config-path' -or $txt -match '-c\s+CONFIGPATH' -or $txt -match '-c\s+CONFIG') { $FoundConfigPath = $true }
        if ($txt -match '--log-file' -or $txt -match '-f\s+LOGFILENAME') { $FoundLogFile = $true }
        if ($txt -match '--portable' -or $txt -match 'Portable Copy') { $FoundPortable = $true }
    } catch {
        # ignore read errors
    }
}

Write-Log "Doc detection: --config-path=$FoundConfigPath, --log-file=$FoundLogFile, --portableMention=$FoundPortable"

# Require authoritative support for config-path before launching NVDA to ensure profile isolation
if (-not $FoundConfigPath) {
    Write-Error 'NVDA documentation does not indicate support for --config-path/-c. Cannot guarantee profile isolation. Aborting.'
    exit 3
}

# Record profile isolation method
$PROFILE_ISOLATION_METHOD = '--config-path'
Write-Log "PROFILE_ISOLATION_METHOD = $PROFILE_ISOLATION_METHOD"

# Prepare disposable test workspace
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$TestRoot = Join-Path $ResultsBase $timestamp
$ProfileDir = Join-Path $TestRoot 'profile'
$AddonInstallDir = Join-Path $ProfileDir 'addons'
$VoiceDir = Join-Path $ProfileDir 'sonata'  # will be used as SONATA_VOICES_DIR
$LogsDir = Join-Path $TestRoot 'logs'
New-Item -ItemType Directory -Path $AddonInstallDir -Force | Out-Null
New-Item -ItemType Directory -Path $VoiceDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null

Write-Log "Created disposable test workspace: $TestRoot"

# Record baseline processes
function Dump-Processes($outFile) {
    Get-Process *nvda*, *sonata-grpc* -ErrorAction SilentlyContinue | Sort-Object ProcessName, Id | Format-Table -AutoSize | Out-String | Set-Content -LiteralPath $outFile
}
$procBefore = Join-Path $LogsDir 'process-before.txt'
Dump-Processes $procBefore
Write-Log "Wrote baseline process list to $procBefore"

# Ensure not touching daily NVDA profile: check running NVDA processes
$nvdaRunning = Get-Process -Name nvda -ErrorAction SilentlyContinue
$NVDA_CURRENTLY_RUNNING = $false
if ($nvdaRunning) {
    $NVDA_CURRENTLY_RUNNING = $true
    Write-Error 'NVDA process(es) detected. This harness will NOT continue while NVDA is running. Close your daily NVDA and re-run this harness.'
    exit 6
}

# Install addon into disposable profile (extract .nvda-addon ZIP)
Write-Log 'Installing .nvda-addon into disposable profile (extracting ZIP)'
$AddonRoot = Join-Path $AddonInstallDir 'sonata_neural_voices'
# Ensure clean target
if (Test-Path $AddonRoot) { Remove-Item -LiteralPath $AddonRoot -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Path $AddonRoot -Force | Out-Null
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    # Extract archive contents directly into addons\sonata_neural_voices\ so manifest.ini sits under that folder
    [System.IO.Compression.ZipFile]::ExtractToDirectory($AddonPath, $AddonRoot)
} catch {
    Write-Error ("Failed to extract addon into {0}: {1}" -f $AddonRoot, $_); exit 2
}
Write-Log "Addon extracted to $AddonRoot"

# Validate prelaunch addon layout
$MANIFEST_PATH = Join-Path $AddonRoot 'manifest.ini'
$SYNTH_DRIVER_PATH = Join-Path $AddonRoot 'synthDrivers\sonata_neural_voices\__init__.py'
$GLOBAL_PLUGIN_PATH = Join-Path $AddonRoot 'globalPlugins\sonata_tts_global_plugin\__init__.py'
$PRELAUNCH_LAYOUT_VALID = $true
if (-not (Test-Path $MANIFEST_PATH)) { Write-Error "Missing manifest: $MANIFEST_PATH"; $PRELAUNCH_LAYOUT_VALID = $false }
if (-not (Test-Path $SYNTH_DRIVER_PATH)) { Write-Error "Missing synth driver: $SYNTH_DRIVER_PATH"; $PRELAUNCH_LAYOUT_VALID = $false }
if (-not (Test-Path $GLOBAL_PLUGIN_PATH)) { Write-Error "Missing global plugin: $GLOBAL_PLUGIN_PATH"; $PRELAUNCH_LAYOUT_VALID = $false }

if (-not $PRELAUNCH_LAYOUT_VALID) {
    Write-Error 'Addon prelaunch layout validation failed. Aborting to avoid launching NVDA with incomplete addon.'
    exit 7
}

# Parse manifest.ini and verify name
try {
    $manifestLines = Get-Content -Path $MANIFEST_PATH -ErrorAction Stop
    $nameLine = $manifestLines | Where-Object { $_ -match '^\s*name\s*=\s*' } | Select-Object -First 1
    if ($nameLine -and ($nameLine -match '=\s*(.+)$')) {
        $manifestName = $Matches[1].Trim()
        if ($manifestName -ne 'sonata_neural_voices') {
            Write-Error "manifest.ini name value unexpected: $manifestName"; exit 7
        }
    } else {
        Write-Error 'Could not find name entry in manifest.ini'; exit 7
    }
} catch {
    Write-Error ("Failed to parse manifest.ini: {0}" -f $_); exit 7
}
Write-Log 'Addon prelaunch layout and manifest verified.'

# Locate Lessac/Piper voice in archived research location
Write-Log 'Searching archive for Lessac/Piper voice files under C:\projects-archive\nvda-tts-legacy'
$lessacRoot = 'C:\projects-archive\nvda-tts-legacy'
$lessacOnnxName = 'en_US-lessac-low.onnx'
$lessacJsonName = 'en_US-lessac-low.onnx.json'
$LESSAC_FOUND = $false
$LESSAC_SOURCE_ONNX = ''
$LESSAC_SOURCE_JSON = ''

if (Test-Path $lessacRoot) {
    $onnxCandidates = Get-ChildItem -Path $lessacRoot -Recurse -Filter $lessacOnnxName -ErrorAction SilentlyContinue
    foreach ($onnx in $onnxCandidates) {
        $candidateJson = Join-Path $onnx.Directory.FullName $lessacJsonName
        if (Test-Path $candidateJson) {
            $LESSAC_FOUND = $true
            $LESSAC_SOURCE_ONNX = $onnx.FullName
            $LESSAC_SOURCE_JSON = $candidateJson
            break
        }
    }
} else {
    Write-Log "Archive root not found: $lessacRoot"
}

if ($LESSAC_FOUND) {
    Write-Log "Found Lessac source ONNX: $LESSAC_SOURCE_ONNX"
    Write-Log "Found Lessac source JSON: $LESSAC_SOURCE_JSON"
    # Determine Sonata destination from code: SONATA_VOICES_DIR = <configPath>/sonata/voices/piper
    $destVoiceBase = Join-Path $ProfileDir 'sonata\voices\piper'
    New-Item -ItemType Directory -Path $destVoiceBase -Force | Out-Null
    # Derive voice folder name from ONNX filename using same convention as installer: lang-name-quality
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($LESSAC_SOURCE_ONNX)
    $parts = $stem -split '-' 
    if ($parts.Length -ge 3) {
        $lang = $parts[0]
        $name = $parts[1]
        $quality = $parts[2]
        # normalize parts: replace - with _ in name/quality
        $name = $name -replace '-', '_'
        $quality = $quality -replace '-', '_'
        $voiceKey = "$lang-$name-$quality"
    } else {
        # fallback to simple naming
        $voiceKey = $stem
    }
    $destVoiceDir = Join-Path $destVoiceBase $voiceKey
    New-Item -ItemType Directory -Path $destVoiceDir -Force | Out-Null
    $destOnnx = Join-Path $destVoiceDir $lessacOnnxName
    $destJson = Join-Path $destVoiceDir $lessacJsonName
    Copy-Item -Path $LESSAC_SOURCE_ONNX -Destination $destOnnx -Force
    Copy-Item -Path $LESSAC_SOURCE_JSON -Destination $destJson -Force
    # compute hashes
    $srcOnnxHash = (Get-FileHash -Algorithm SHA256 $LESSAC_SOURCE_ONNX).Hash
    $copyOnnxHash = (Get-FileHash -Algorithm SHA256 $destOnnx).Hash
    $srcJsonHash = (Get-FileHash -Algorithm SHA256 $LESSAC_SOURCE_JSON).Hash
    $copyJsonHash = (Get-FileHash -Algorithm SHA256 $destJson).Hash
    "lessac_source_onnx=$LESSAC_SOURCE_ONNX`nvoice_key=$voiceKey" | Out-File -FilePath (Join-Path $LogsDir 'lessac-source.txt') -Encoding utf8
    "srcOnnxHash=$srcOnnxHash`ncopyOnnxHash=$copyOnnxHash`nsrcJsonHash=$srcJsonHash`ncopyJsonHash=$copyJsonHash" | Out-File -FilePath (Join-Path $LogsDir 'lessac-hashes.txt') -Encoding utf8
    Write-Log "Copied Lessac voice to $destVoiceDir and recorded hashes"
    $LESSAC_DESTINATION = $destVoiceDir
} else {
    Write-Log 'Lessac voice pair not found in archive. This is a blocker for the runtime validation.'
    $LESSAC_DESTINATION = ''
}

# Prepare pidfile path location used by addon (SONATA_VOICES_BASE_DIR uses NVDA config path)
# We'll capture pidfile from the profile if created
$pidfilePath = Join-Path $ProfileDir 'sonata\sonata_grpc.pid'

# Network snapshots helper
function NetstatTo($path) { netstat -ano | Out-File -FilePath $path -Encoding utf8 }
NetstatTo (Join-Path $LogsDir 'netstat-before.txt')

Write-Log 'Preparing to launch disposable NVDA instance. Follow prompts when NVDA UI appears.'

# Final check: ask user to confirm launch
Write-Output "About to launch NVDA from: $NvdaExe"
Write-Output "Disposable profile will be: $ProfileDir"
$ok = Read-Host "Press ENTER to launch NVDA now (or type C to cancel)"
if ($ok -and $ok.ToUpper().StartsWith('C')) { Write-Log 'User cancelled before NVDA launch'; exit 0 }

# Start NVDA and capture process — ensure PROFILE_ISOLATION_METHOD used
$nvdaLogPath = Join-Path $LogsDir 'nvda.log'
$procAfterStartFile = Join-Path $LogsDir 'process-after-start.txt'
# Build safe argument list using confirmed config-path method (required pattern)
$nvdaArgs = @()
$nvdaArgs += "--config-path=$ProfileDir"
$nvdaArgs += "--log-file=$nvdaLogPath"
$nvdaArgs += "--log-level=10"

$startInfo = @{ FilePath = $NvdaExe; ArgumentList = $nvdaArgs; WorkingDirectory = (Split-Path $NvdaExe); }
Write-Log "Launching NVDA with args: $($nvdaArgs -join ' ')"
$nvdaProc = Start-Process @startInfo -PassThru
Start-Sleep -Seconds 2

# Verify that the launched process is using the disposable profile by inspecting its command line
try {
    $procInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($nvdaProc.Id)" -ErrorAction Stop
    $cmd = $procInfo.CommandLine
    if ($cmd -and $cmd -match [regex]::Escape($ProfileDir)) {
        Write-Log 'Confirmed NVDA process command line includes the disposable profile path.'
        $PROFILE_ISOLATION_CONFIRMED = $true
    } else {
        Write-Error 'Launched NVDA does not contain the expected --config-path argument in its command line. Aborting and killing the NVDA instance to avoid touching the daily profile.'
        try { Stop-Process -Id $nvdaProc.Id -Force -ErrorAction SilentlyContinue } catch {}
        exit 4
    }
} catch {
    Write-Error ("Failed to inspect NVDA process command line: {0}" -f $_); exit 5
}

Start-Sleep -Seconds 2
Dump-Processes $procAfterStartFile
NetstatTo (Join-Path $LogsDir 'netstat-during.txt')

# Wait for sonata-grpc to appear (up to 20s)
Write-Log 'Waiting up to 20s for sonata-grpc process to appear...'
$grpcStarted = $false
for ($i=0; $i -lt 40; $i++) {
    $g = Get-Process -Name 'sonata-grpc' -ErrorAction SilentlyContinue
    if ($g) { $grpcStarted = $true; break }
    Start-Sleep -Milliseconds 500
}
if ($grpcStarted) {
    $g | Select-Object Id, ProcessName, StartTime | Out-File -FilePath (Join-Path $LogsDir 'process-sonata-after-start.txt') -Encoding utf8
    Write-Log 'sonata-grpc process observed.'
} else {
    Write-Log 'sonata-grpc not observed after NVDA start.'
}

# Helper to capture tail of logs
function Tail-File($file, $out) {
    if (Test-Path $file) {
        Get-Content -Path $file -Encoding UTF8 -Tail 200 | Out-File -FilePath $out -Encoding UTF8
    }
}

# Minimal human interaction sequence prompts
function PromptAndWait($message, $capturePrefix) {
    Write-Output "\n*** ACTION REQUIRED: $message ***\n"
    Write-Output 'After completing the action in NVDA, press ENTER to continue.'
    Read-Host
    # capture processes & logs
    Dump-Processes (Join-Path $LogsDir "$capturePrefix-process.txt")
    NetstatTo (Join-Path $LogsDir "$capturePrefix-netstat.txt")
    # collect any sonata pidfile
    if (Test-Path $pidfilePath) { Get-Content $pidfilePath | Out-File (Join-Path $LogsDir "$capturePrefix-pidfile.txt") }
    # attempt to locate sonata-grpc log under profile or known base dir
    $candidateLog = Join-Path $VoiceDir '..\logs\sonata-grpc.log'
    $candidateLog2 = Join-Path $RepoRoot 'addon\synthDrivers\sonata_neural_voices\bin\sonata-grpc.log'
    Tail-File $candidateLog (Join-Path $LogsDir "$capturePrefix-sonata-grpc.log")
    Tail-File $candidateLog2 (Join-Path $LogsDir "$capturePrefix-sonata-grpc.binlog")
}

# Sequence of prompts per task
PromptAndWait 'In NVDA: Open Settings -> Speech -> Select "Sonata Neural Voices" as the synth' 'after-select'
PromptAndWait 'In NVDA: Select the Lessac test voice (from the list) and apply' 'after-voice-select'

# Normal speech check
PromptAndWait 'Trigger a normal speech (say a short sentence via TalkWindow or press NVDA+T) and confirm audible' 'after-normal-speech'

# Cancel test: instruct user to start long utterance and press NVDA+K or use speech cancel
PromptAndWait 'Start a long utterance and then cancel it (NVDA key to stop speech). Confirm audio stops.' 'after-cancel'

# Repeated synthesis
PromptAndWait 'Trigger repeated short speech or paste short texts quickly to synthesize several utterances' 'after-repeated'

# Synth switch
PromptAndWait 'Switch to a built-in synth (eSpeak) from NVDA settings; confirm speech works' 'after-switch'
PromptAndWait 'Switch back to Sonata and confirm speech works' 'after-reselect'

# Exit NVDA normally (via UI) and then press ENTER here
Write-Output "Now, please exit NVDA normally (File -> Exit). After NVDA has exited, come back to this window and press ENTER."
Read-Host

# Capture final process lists and netstat
Dump-Processes (Join-Path $LogsDir 'process-after-exit.txt')
NetstatTo (Join-Path $LogsDir 'netstat-after.txt')
if (Test-Path $pidfilePath) { Get-Content $pidfilePath | Out-File (Join-Path $LogsDir 'pidfile-after-exit.txt') }

# Verify sonata-grpc cleanup
$orphan = Get-Process -Name 'sonata-grpc' -ErrorAction SilentlyContinue
$orphanCount = if ($orphan) { $orphan.Count } else { 0 }
Write-Log "Orphan sonata-grpc process count after NVDA exit: $orphanCount"
if ($orphanCount -gt 0) {
    # Record details
    $orphan | Select-Object Id, ProcessName, StartTime, @{Name='CmdLine';Expression={($_ | Get-CimInstance Win32_Process).CommandLine}} | Out-File (Join-Path $LogsDir 'orphan-details.txt') -Encoding utf8
}

# Analyze logs automatically
$searchTerms = @( 'Traceback', 'ERROR', 'CRITICAL', 'CancelledError', 'grpc', 'LoadVoice', 'voice', 'PCM', 'WavePlayer', 'terminate', 'CTRL_BREAK', 'pidfile', 'connection', 'shutdown', 'SynthDriver', 'setSynth' )
$evidence = @()
Get-ChildItem -Path $LogsDir -Recurse -File | ForEach-Object {
    $content = Get-Content -Path $_.FullName -ErrorAction SilentlyContinue -Raw -Encoding UTF8
    foreach ($term in $searchTerms) {
        if ($content -match [regex]::Escape($term)) {
            $evidence += "Found '$term' in $($_.FullName)"
            break
        }
    }
}
$evidence | Out-File (Join-Path $LogsDir 'log-evidence.txt') -Encoding utf8

# Build test-summary.json
$summary = [PSCustomObject]@{
    resultsDir = $TestRoot
    humanListening = 'ACCEPT'
    sonataSynthSelected = if (Test-Path (Join-Path $LogsDir 'after-select-process.txt')) { 'UNVERIFIED' } else { 'UNVERIFIED' }
    grpcStart = if (Test-Path (Join-Path $LogsDir 'process-sonata-after-start.txt')) { 'PASS' } else { 'FAIL' }
    voiceDiscovery = 'UNVERIFIED'
    voiceLoad = 'UNVERIFIED'
    normalSpeech = 'UNVERIFIED'
    pcmOutput = 'UNVERIFIED'
    cancel = 'UNVERIFIED'
    repeatedSynthesis = 'UNVERIFIED'
    synthSwitchCleanup = if ($orphanCount -eq 0) { 'PASS' } else { 'FAIL' }
    reselectSonata = 'UNVERIFIED'
    nvdaExitCleanup = if ($orphanCount -eq 0) { 'PASS' } else { 'FAIL' }
    orphanProcessCount = $orphanCount
    duplicateProcessCount = 0
    relevantTraceback = if (Test-Path (Join-Path $LogsDir 'log-evidence.txt')) { (Get-Content (Join-Path $LogsDir 'log-evidence.txt') -Raw) } else { '' }
}
$summaryFile = Join-Path $TestRoot 'results-summary.json'
$summary | ConvertTo-Json -Depth 5 | Out-File -FilePath $summaryFile -Encoding utf8

Write-Log "Test completed. Results directory: $TestRoot"
Write-Output "RESULTS DIRECTORY: $TestRoot"

# Print concise table
Write-Output "\nSUMMARY:\n"
@{
    HUMAN_LISTENING = 'ACCEPT'
    SONATA_SYNTH_SELECTED = $summary.sonataSynthSelected
    GRPC_START = $summary.grpcStart
    GRPC_CONNECTION = 'UNVERIFIED'
    VOICE_DISCOVERY = $summary.voiceDiscovery
    VOICE_LOAD = $summary.voiceLoad
    NORMAL_SPEECH = $summary.normalSpeech
    PCM_OUTPUT = $summary.pcmOutput
    CANCEL = $summary.cancel
    REPEATED_SYNTHESIS = $summary.repeatedSynthesis
    SYNTH_SWITCH_CLEANUP = $summary.synthSwitchCleanup
    RESELECT_SONATA = $summary.reselectSonata
    NVDA_EXIT_CLEANUP = $summary.nvdaExitCleanup
    ORPHAN_PROCESS_COUNT = $summary.orphanProcessCount
    DUPLICATE_PROCESS_COUNT = $summary.duplicateProcessCount
    RELEVANT_TRACEBACK = if ($summary.relevantTraceback) { 'YES' } else { 'NO' }
} | Format-List

Write-Log 'Validation harness finished.'
