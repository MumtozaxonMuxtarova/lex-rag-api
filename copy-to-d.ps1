# Run this yourself after extracting the archive if direct saving to D: is unavailable.
param([string]$DestinationRoot = 'D:\pdp univer 4 kurs\1 semester\AI\06.11.2026')
$ErrorActionPreference = 'Stop'
$sourceRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$targetRoot = [IO.Path]::GetFullPath((Join-Path $DestinationRoot 'lex-rag-api'))
if (-not (Test-Path -LiteralPath $DestinationRoot -PathType Container)) { throw 'Destination parent folder does not exist.' }
if (Test-Path -LiteralPath $targetRoot) { throw 'lex-rag-api already exists at the destination. Existing work was not overwritten.' }
if ($targetRoot.StartsWith($sourceRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Destination cannot be inside source.' }
$items = Get-ChildItem -LiteralPath $sourceRoot -Recurse -Force -File | Where-Object {
    $relative = $_.FullName.Substring($sourceRoot.Length + 1)
    $relative -notmatch '(^|[\\/])(\.git|\.runtime|__pycache__|\.pytest_cache)([\\/]|$)' -and
    $_.Name -ne '.env' -and $_.Extension -notin '.sqlite3','.tmp'
}
New-Item -ItemType Directory -Path $targetRoot | Out-Null
foreach ($item in $items) {
    $relative = $item.FullName.Substring($sourceRoot.Length + 1)
    $destination = Join-Path $targetRoot $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $item.FullName -Destination $destination
}
Write-Host ('Project copied to: ' + $targetRoot)
