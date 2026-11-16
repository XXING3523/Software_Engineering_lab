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

Compress-Archive -Path $packagePath -DestinationPath $zipPath -CompressionLevel Optimal
Write-Output "已生成：$zipPath"
