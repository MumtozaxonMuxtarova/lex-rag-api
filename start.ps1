param(
    [string]$PythonPath,
    [ValidateRange(1024,65535)][int]$Port = 8000,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (-not $PythonPath) {
    $candidates = @()
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike '*WindowsApps*') { $candidates += $pythonCommand.Source }
    $candidates += (Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe')
    $PythonPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python 3.11+ topilmadi. Pythonni o‘rnating yoki -PythonPath orqali python.exe manzilini bering."
}
& $PythonPath -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
$runtime = Join-Path $PSScriptRoot '.runtime'
$packages = Join-Path $runtime 'packages'
$tempDir = Join-Path $runtime 'temp'
New-Item -ItemType Directory -Force -Path $packages,$tempDir | Out-Null
$env:TEMP = $tempDir
$env:TMP = $tempDir
$env:PYTHONPATH = $packages + [IO.Path]::PathSeparator + $PSScriptRoot
$requirementHash = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'requirements.txt') -Algorithm SHA256).Hash
$marker = Join-Path $runtime 'requirements.sha256'
if (-not (Test-Path -LiteralPath $marker) -or (Get-Content -Raw -LiteralPath $marker).Trim() -ne $requirementHash) {
    Write-Host "Kutubxonalar o‘rnatilmoqda (birinchi ishga tushirishda internet kerak)..."
    & $PythonPath -m pip install --upgrade --target $packages -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Kutubxonalarni o‘rnatish bajarilmadi." }
    Set-Content -LiteralPath $marker -Value $requirementHash -Encoding ascii
}
$envFile = Join-Path $PSScriptRoot '.env'
if (-not $env:RAG_API_KEY -and (Test-Path -LiteralPath $envFile)) {
    $keyLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -match '^RAG_API_KEY=' } | Select-Object -First 1
    if ($keyLine) { $env:RAG_API_KEY = $keyLine.Substring(12).Trim() }
}
if (-not $env:RAG_API_KEY) {
    $env:RAG_API_KEY = & $PythonPath -c 'import secrets; print(secrets.token_urlsafe(32))'
    if ($LASTEXITCODE -ne 0) { throw 'Mahalliy API kaliti yaratilmadi.' }
    Set-Content -LiteralPath $envFile -Value ('RAG_API_KEY=' + $env:RAG_API_KEY) -Encoding ascii
}
if (-not (Test-Path -LiteralPath 'data/lex.jsonl')) {
    if (Test-Path -LiteralPath 'data/corpus.zip') {
        Write-Host 'Tayyor lex.uz korpusi ochilmoqda...'
        Expand-Archive -LiteralPath 'data/corpus.zip' -DestinationPath 'data' -Force
    }
}
if (-not (Test-Path -LiteralPath 'data/lex.jsonl')) {
    Write-Host 'Haqiqiy lex.uz hujjatlari yuklanmoqda...'
    & $PythonPath -m app.ingest --history-since 2025-01-01
    if ($LASTEXITCODE -ne 0) { throw 'Manbalar importi bajarilmadi.' }
}
Write-Host ''
Write-Host ('Sayt: http://127.0.0.1:' + $Port)
Write-Host 'Saytdagi APIga ulanish oynasiga .env faylidagi RAG_API_KEY qiymatini kiriting.'
Write-Host "To‘xtatish: Ctrl+C"
if ($NoBrowser) {
    & $PythonPath -m app.launch --port $Port --no-browser
} else {
    & $PythonPath -m app.launch --port $Port
}
exit $LASTEXITCODE
