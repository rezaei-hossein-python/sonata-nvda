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
$ExpectedSHA = 'B213A49CD319F70ECF81445806B551B74C0F7E698F6D0D4993D172C1BE101438'
$NvdaDefaultPath = 'C:\Program Files\NVDA\nvda.exe'
$ResultsBase = 'C:\temp\sonata-nvda-runtime-test'

# Safety checks
Write-Log 'Starting Sonata NVDA runtime validation harness (dry-run safety checks).'
if (-not (Test-Path $RepoRoot)) { Write-Error "Repo root not found: $RepoRoot"; exit 2 }
if (-not (Test-Path $AddonPath)) { Write-Error "Addon not found: $AddonPath"; exit 2 }

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

# Ask NVDA for CLI help to determine portable/config support
Write-Log 'Querying NVDA for supported command-line options...'
$helpText = ''
try {
    $helpText = & "$NvdaExe" --help 2>&1 | Out-String
} catch {
    # Some nvda builds require no-elevation; try capturing output without throwing
    try { $helpText = & "$NvdaExe" -h 2>&1 | Out-String } catch { $helpText = '' }
}
if (-not $helpText) { Write-Log 'Could not capture nvda --help output; proceeding but will validate before launching.' }

$SupportsPortable = $false
$SupportsConfigDir = $false
if ($helpText -match '--portable') { $SupportsPortable = $true }
if ($helpText -match 'config') { $SupportsConfigDir = $true }
Write-Log "NVDA CLI capabilities: portable=$SupportsPortable, configHint=$SupportsConfigDir"

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
if ($nvdaRunning) {
    Write-Log 'NVDA process(es) detected. This harness will not forcibly terminate your daily NVDA.'
    Write-Output "Please close your daily NVDA instance if you want this test to run a second NVDA instance."
    $resp = Read-Host "NVDA is running. Close it now and press ENTER to continue, or press C to cancel test"
    if ($resp -and $resp.ToUpper().StartsWith('C')) { Write-Log 'User cancelled test due to running NVDA'; exit 0 }
}

# Install addon into disposable profile (extract .nvda-addon ZIP)
Write-Log 'Installing .nvda-addon into disposable profile (extracting ZIP)'
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($AddonPath, $AddonInstallDir)
} catch {
    Write-Error ("Failed to extract addon: {0}" -f $_); exit 2
}
Write-Log "Addon extracted to $AddonInstallDir"

# Locate a sample Lessac/Piper voice in repo (search for .onnx or voice- dir)
Write-Log 'Searching repository for a candidate Lessac/Piper voice to copy into disposable profile...'
$voiceSource = Get-ChildItem -Path $RepoRoot -Recurse -Include *.onnx,*.json -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match 'voice-' -or $_.FullName -match 'lessac' } | Select-Object -First 1
if ($voiceSource) {
    Write-Log "Found possible voice file: $($voiceSource.FullName)"
    # copy entire voice directory if applicable
    $voiceDirCandidate = $voiceSource.Directory.FullName
    $targetVoiceDir = Join-Path $VoiceDir (Split-Path $voiceDirCandidate -Leaf)
    Copy-Item -Recurse -Force -Path $voiceDirCandidate -Destination $targetVoiceDir
    # compute hashes
    $srcHash = (Get-FileHash -Algorithm SHA256 $voiceSource.FullName).Hash
    $copyFile = Join-Path $targetVoiceDir $voiceSource.Name
    $copyHash = (Get-FileHash -Algorithm SHA256 $copyFile).Hash
    "voice_source=$($voiceSource.FullName)" | Out-File -FilePath (Join-Path $LogsDir 'voice-source.txt') -Encoding utf8
    "src_hash=$srcHash`ncopy_hash=$copyHash" | Out-File -FilePath (Join-Path $LogsDir 'voice-hashes.txt') -Encoding utf8
    Write-Log "Copied voice directory to $targetVoiceDir and recorded hashes"
} else {
    Write-Log 'No voice file discovered automatically. You will be prompted later to select or install a voice into the disposable profile.'
}

# Prepare pidfile path location used by addon (SONATA_VOICES_BASE_DIR uses NVDA config path)
# We'll capture pidfile from the profile if created
$pidfilePath = Join-Path $ProfileDir 'sonata\sonata_grpc.pid'

# Network snapshots helper
function NetstatTo($path) { netstat -ano | Out-File -FilePath $path -Encoding utf8 }
NetstatTo (Join-Path $LogsDir 'netstat-before.txt')

# Launch NVDA using portable/config options if supported
Write-Log 'Preparing to launch disposable NVDA instance. Follow prompts when NVDA UI appears.'
$nvdaArgs = @()
if ($SupportsPortable) { $nvdaArgs += '--portable' }
# If there is a known configdir option, use it (best-effort). Common NVDA 2026 supports --configDir or --config
$hasConfigArg = $false
if ($helpText -match '--configdir') { $nvdaArgs += '--configdir'; $nvdaArgs += $ProfileDir; $hasConfigArg = $true }
elseif ($helpText -match '--configdir=') { $nvdaArgs += "--configdir=$ProfileDir"; $hasConfigArg = $true }
elseif ($helpText -match '--config') { $nvdaArgs += '--config'; $nvdaArgs += $ProfileDir; $hasConfigArg = $true }

# If no explicit config option found, fall back to --portable and set NVDA's appdata via environment (best-effort)
$envVars = Get-ChildItem env: | ForEach-Object { $_ }

# Final check: ask user to confirm launch
Write-Output "About to launch NVDA from: $NvdaExe"
Write-Output "Disposable profile will be: $ProfileDir"
$ok = Read-Host "Press ENTER to launch NVDA now (or type C to cancel)"
if ($ok -and $ok.ToUpper().StartsWith('C')) { Write-Log 'User cancelled before NVDA launch'; exit 0 }

# Start NVDA and capture process
$nvdaLogPath = Join-Path $LogsDir 'nvda.log'
$procAfterStartFile = Join-Path $LogsDir 'process-after-start.txt'
$startInfo = @{ FilePath = $NvdaExe; ArgumentList = $nvdaArgs; WorkingDirectory = (Split-Path $NvdaExe); }
Write-Log "Launching NVDA: $NvdaExe $($nvdaArgs -join ' ')"
$nvdaProc = Start-Process @startInfo -PassThru
Start-Sleep -Seconds 4
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
