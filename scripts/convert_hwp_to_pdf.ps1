<#
.SYNOPSIS
  한컴오피스 2020 COM 자동화로 HWP 버전을 검색 가능한 PDF로 변환한다.
.DESCRIPTION
  sources/raw는 수정하지 않고 corpus/pdf에 파생본을 생성한다. 기존 PDF는 재사용하며
  긴 원본 경로는 tmp의 짧은 임시 경로로 copy2-equivalent 복사 후 연다.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Force,
    [int]$Limit = 0,
    [int]$ShardIndex = 0,
    [int]$ShardCount = 1
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VersionsPath = Join-Path $RepoRoot 'metadata\versions.jsonl'
$ManifestName = if ($ShardCount -gt 1) { "hwp_pdf_manifest.shard-$ShardIndex-of-$ShardCount.jsonl" } else { 'hwp_pdf_manifest.jsonl' }
$ManifestPath = Join-Path $RepoRoot ("metadata\" + $ManifestName)
$TempInput = Join-Path $RepoRoot 'tmp\hwp_conversion_input'
$TempOutput = Join-Path $RepoRoot 'tmp\hwp_conversion_output'
New-Item -ItemType Directory -Force -Path $TempInput, $TempOutput | Out-Null

if (-not (Test-Path -LiteralPath $VersionsPath)) {
    throw "버전 메타데이터가 없습니다: $VersionsPath"
}

$Versions = @(Get-Content -Encoding UTF8 -LiteralPath $VersionsPath |
    ForEach-Object { $_ | ConvertFrom-Json } |
    Where-Object { $_.source_file -match '(?i)\.hwp$' -and $_.access_level -eq 'public' })
if ($ShardCount -lt 1 -or $ShardIndex -lt 0 -or $ShardIndex -ge $ShardCount) { throw '잘못된 shard 설정입니다.' }
if ($ShardCount -gt 1) {
    $AllVersions = $Versions
    $Versions = @()
    for ($i = 0; $i -lt $AllVersions.Count; $i++) {
        if ($i % $ShardCount -eq $ShardIndex) { $Versions += $AllVersions[$i] }
    }
}
if ($Limit -gt 0) { $Versions = @($Versions | Select-Object -First $Limit) }

function New-HwpApplication {
    $App = New-Object -ComObject HWPFrame.HwpObject
    try { $App.XHwpWindows.Item(0).Visible = $false } catch {}
    return $App
}

function Close-HwpApplication($App) {
    if ($null -eq $App) { return }
    try { $App.Quit() } catch {}
    try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($App) } catch {}
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

$Results = [System.Collections.Generic.List[object]]::new()
$App = $null
$Converted = 0
$Reused = 0
$Failed = 0
$Index = 0

try {
    if (-not $DryRun) { $App = New-HwpApplication }
    foreach ($Version in $Versions) {
        $Index++
        $Source = Join-Path $RepoRoot $Version.source_file
        $Bucket = if ($Version.document_type -eq 'regulation') { 'regulations' } else { 'guidelines' }
        $TargetDirectory = Join-Path $RepoRoot ("corpus\pdf\{0}\{1}" -f $Bucket, $Version.document_id)
        $Target = Join-Path $TargetDirectory ($Version.version_id + '.pdf')
        $Status = 'planned'
        $ErrorMessage = $null

        try {
            if (-not (Test-Path -LiteralPath $Source)) { throw "HWP 원본이 없습니다: $Source" }
            if ((Test-Path -LiteralPath $Target) -and -not $Force) {
                $Status = 'reused'
                $Reused++
            } elseif (-not $DryRun) {
                New-Item -ItemType Directory -Force -Path $TargetDirectory | Out-Null
                $OpenPath = $Source
                $ShortInput = Join-Path $TempInput ($Version.sha256 + '.hwp')
                if ($Source.Length -gt 230) {
                    Copy-Item -LiteralPath $Source -Destination $ShortInput -Force
                    $OpenPath = $ShortInput
                }
                $TempPdf = Join-Path $TempOutput ($Version.sha256 + '.pdf')
                if (Test-Path -LiteralPath $TempPdf) { Remove-Item -LiteralPath $TempPdf -Force }
                $Opened = $App.Open($OpenPath, 'HWP', 'forceopen:true')
                if (-not $Opened) { throw '한컴오피스에서 문서를 열지 못했습니다.' }
                $Saved = $App.SaveAs($TempPdf, 'PDF', '')
                try { $App.Clear(1) } catch {}
                if (-not $Saved -or -not (Test-Path -LiteralPath $TempPdf)) { throw 'PDF 저장에 실패했습니다.' }
                Move-Item -LiteralPath $TempPdf -Destination $Target -Force
                if (Test-Path -LiteralPath $ShortInput) { Remove-Item -LiteralPath $ShortInput -Force }
                $Status = 'converted'
                $Converted++
            }
        } catch {
            $Status = 'failed'
            $ErrorMessage = $_.Exception.Message
            $Failed++
            try { $App.Clear(1) } catch {}
        }

        $Results.Add([pscustomobject]@{
            version_id = $Version.version_id
            document_id = $Version.document_id
            document_type = $Version.document_type
            source_file = $Version.source_file
            source_sha256 = $Version.sha256
            pdf_file = (Resolve-Path -LiteralPath $Target -Relative -ErrorAction SilentlyContinue)
            status = $Status
            error = $ErrorMessage
        })

        if (-not $DryRun -and $Index % 100 -eq 0) {
            Close-HwpApplication $App
            $App = New-HwpApplication
        }
        if ($Index % 25 -eq 0 -or $Index -eq $Versions.Count) {
            Write-Output ("진행 {0}/{1} 변환={2} 재사용={3} 실패={4}" -f $Index, $Versions.Count, $Converted, $Reused, $Failed)
        }
    }
} finally {
    Close-HwpApplication $App
}

if (-not $DryRun) {
    $Lines = @($Results | ForEach-Object {
        if ($_.pdf_file) { $_.pdf_file = ($_.pdf_file -replace '^\.\\', '' -replace '\\', '/') }
        $_ | ConvertTo-Json -Compress -Depth 6
    })
    [IO.File]::WriteAllLines($ManifestPath, $Lines, [Text.UTF8Encoding]::new($false))
}

Write-Output ("완료 대상={0} 변환={1} 재사용={2} 실패={3} dry_run={4}" -f $Versions.Count, $Converted, $Reused, $Failed, $DryRun)
if ($Failed -gt 0) { exit 1 }
