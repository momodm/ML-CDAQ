param(
    [string]$Python = 'C:\Users\t7952235\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',
    [string]$Node = 'C:\Users\t7952235\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
if (!(Test-Path -LiteralPath $Python) -or !(Test-Path -LiteralPath $Node)) { throw '请用 -Python 和 -Node 指定本机可用运行时的完整路径。' }
if (!(Test-Path -LiteralPath "$projectRoot\frontend\node_modules\vite\bin\vite.js")) { throw '请先按系统运行说明安装前端依赖。' }
foreach ($port in 8000,5173) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,$port)
    $listener.ExclusiveAddressUse = $true
    try { $listener.Start() } catch { throw "端口 $port 无法使用，请先关闭已有服务或检查本机权限。" } finally { $listener.Stop() }
}
New-Item -ItemType Directory -Path "$projectRoot\.runtime\m5_temp" -Force | Out-Null
$env:TEMP = "$projectRoot\.runtime\m5_temp"
$env:TMP = $env:TEMP
$backendProcess = $null
$frontendProcess = $null
try {
    $backendProcess = Start-Process $Python -ArgumentList 'scripts/run_backend.py' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$projectRoot\.runtime\系统后端输出.log" -RedirectStandardError "$projectRoot\.runtime\系统后端错误.log"
    $frontendProcess = Start-Process $Node -ArgumentList 'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort' -WorkingDirectory "$projectRoot\frontend" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$projectRoot\.runtime\系统前端输出.log" -RedirectStandardError "$projectRoot\.runtime\系统前端错误.log"
    Write-Host '前端 http://127.0.0.1:5173 · 后端 http://127.0.0.1:8000/docs'
    Read-Host '按回车停止本脚本启动的两个进程；日志位于 .runtime' | Out-Null
} finally {
    foreach ($process in @($backendProcess,$frontendProcess)) {
        if ($process -and !$process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue }
    }
}
