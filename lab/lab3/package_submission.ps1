param(
    [string]$StudentId = "241220105",
    [string]$Name = "张鑫源"
)

$folderName = "实验3_${StudentId}_${Name}"
$packagePath = Join-Path $PSScriptRoot $folderName
$zipPath = Join-Path $PSScriptRoot "$folderName.zip"

if (-not (Test-Path -LiteralPath $packagePath -PathType Container)) {
    throw "提交目录不存在：$packagePath"
}

$required = @(
    (Join-Path $packagePath "实验报告.pdf"),
    (Join-Path $packagePath "UML"),
    (Join-Path $packagePath "code")
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "缺少提交内容：$path"
    }
}

if (Test-Path -LiteralPath $zipPath) {
    throw "压缩包已存在，为避免覆盖请先手动处理：$zipPath"
}

$stagingRoot = Join-Path $PSScriptRoot ".submission-staging"
$stagingPackage = Join-Path $stagingRoot $folderName
try {
    New-Item -ItemType Directory -Force -Path $stagingPackage | Out-Null
    Copy-Item -LiteralPath (Join-Path $packagePath "实验报告.pdf") -Destination $stagingPackage
    Copy-Item -LiteralPath (Join-Path $packagePath "UML") -Destination $stagingPackage -Recurse
    Copy-Item -LiteralPath (Join-Path $packagePath "code") -Destination $stagingPackage -Recurse
    Compress-Archive -Path $stagingPackage -DestinationPath $zipPath -CompressionLevel Optimal
    Write-Output "已生成：$zipPath"
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
