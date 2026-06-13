<#
.SYNOPSIS
    JPEGLI (libjxl) 构建脚本 — 支持多种构建场景

.DESCRIPTION
    支持以下构建场景:
      - Minimal: 仅编译 cjpegli + djpegli（最快）
      - Standard: 包含 ssimulacra2 开发者工具
      - Full: 包含 benchmark, devtools 等所有组件
      - Debug: Debug 模式构建

.PARAMETER BuildType
    构建类型: Release | Debug | RelWithDebInfo (默认: Release)

.PARAMETER Target
    构建档次: Minimal | Standard | Full | Debug (默认: Standard)

.PARAMETER Clean
    清理之前的构建并重新编译

.PARAMETER NinjaJobs
    并行编译任务数 (默认: 自动检测 CPU 核心数)

.PARAMETER InstallPfx
    安装前缀路径 (默认: 不安装)

.PARAMETER NoVsEnv
    跳过 VS 环境检测（如果你已经运行了 vcvars64.bat）

.EXAMPLE
    .\scripts\build_jpegli.ps1 -Target Minimal
    .\scripts\build_jpegli.ps1 -Target Standard -Clean
    .\scripts\build_jpegli.ps1 -Target Full -BuildType Debug
#>

param(
    [ValidateSet("Release", "Debug", "RelWithDebInfo")]
    [string]$BuildType = "Release",

    [ValidateSet("Minimal", "Standard", "Full", "Debug")]
    [string]$Target = "Standard",

    [switch]$Clean = $false,
    [int]$NinjaJobs = 0,
    [string]$InstallPfx = "",
    [switch]$NoVsEnv = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$ScriptDir/.."
$BuildDir = "$ProjectRoot/build"

# ── VS 环境检测 ──────────────────────────────────────────────────────
if (-not $NoVsEnv) {
    $vsPath = "C:\Program Files\Microsoft Visual Studio\2022\Community"
    $devShellModule = "$vsPath\Common7\Tools\Microsoft.VisualStudio.DevShell.dll"
    if (Test-Path $devShellModule) {
        Import-Module $devShellModule -ErrorAction SilentlyContinue
        Enter-VsDevShell -VsInstallPath $vsPath -SkipAutomaticLocation -DevCmdArguments "-arch=x64" 2>$null
        Write-Host "[INFO] VS 2022 x64 开发环境已加载" -ForegroundColor Green
    } else {
        Write-Host "[WARN] 未找到 VS 2022 DevShell，尝试 vcvars64.bat..." -ForegroundColor Yellow
        $vcvars = "$vsPath\VC\Auxiliary\Build\vcvars64.bat"
        if (Test-Path $vcvars) {
            cmd.exe /c "`"$vcvars`" && set" 2>$null | ForEach-Object {
                if ($_ -match "^(.*?)=(.*)$") { Set-Item -Path "env:$($matches[1])" -Value $matches[2] }
            }
            Write-Host "[INFO] vcvars64.bat 环境已加载" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] 未找到 VS 环境！请确保安装了 Visual Studio 2022" -ForegroundColor Red
            exit 1
        }
    }
}

# ── 并行任务数 ────────────────────────────────────────────────────────
if ($NinjaJobs -le 0) {
    $NinjaJobs = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
    if (-not $NinjaJobs -or $NinjaJobs -le 0) { $NinjaJobs = 4 }
}
$UseJobs = if ($Target -eq "Minimal") { 0 } else { $NinjaJobs }

# ── 打印配置 ──────────────────────────────────────────────────────────
Write-Host @"

╔══════════════════════════════════════════════════════╗
║         JPEGLI 构建脚本 v1.0                         ║
╠══════════════════════════════════════════════════════╣
║  项目目录 : $ProjectRoot
║  构建目录 : $BuildDir
║  构建类型 : $BuildType
║  构建档次 : $Target
║  并行任务 : $NinjaJobs
║  Clean构建 : $Clean
╚══════════════════════════════════════════════════════╝
"@

# ── 清理 ──────────────────────────────────────────────────────────────
if ($Clean -and (Test-Path $BuildDir)) {
    Write-Host "[STEP] 清理构建目录..." -ForegroundColor Cyan
    Remove-Item "$BuildDir/CMakeCache.txt" -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] 已清除 CMake 缓存" -ForegroundColor Green
}

# ── 创建构建目录 ──────────────────────────────────────────────────────
if (-not (Test-Path $BuildDir)) {
    New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
    Write-Host "[STEP] 创建构建目录: $BuildDir" -ForegroundColor Cyan
}

Push-Location $BuildDir

# ── CMake 配置参数 ────────────────────────────────────────────────────
$cmakeArgs = @(
    "..",
    "-G", "Ninja",
    "-DCMAKE_BUILD_TYPE=$BuildType",
    "-DBUILD_TESTING=OFF"
)

switch ($Target) {
    "Minimal" {
        $cmakeArgs += "-DJPEGLI_ENABLE_TOOLS=ON"
        $cmakeArgs += "-DJPEGLI_ENABLE_DEVTOOLS=OFF"
        $cmakeArgs += "-DJPEGLI_ENABLE_BENCHMARK=OFF"
        $cmakeArgs += "-DJPEGLI_ENABLE_FUZZERS=OFF"
        $cmakeArgs += "-DJPEGLI_ENABLE_JNI=OFF"
        $cmakeArgs += "-DJPEGLI_ENABLE_MANPAGES=OFF"
        $cmakeArgs += "-DJPEGLI_ENABLE_DOXYGEN=OFF"
        $cmakeArgs += "-DJPEGLI_ENABLE_OPENEXR=OFF"
        $cmakeArgs += "-DJPEGLI_ENABLE_SJPEG=OFF"
        Write-Host "[CONFIG] Minimal: 仅 cjpegli + djpegli" -ForegroundColor Yellow
    }

    "Standard" {
        $cmakeArgs += "-DJPEGLI_ENABLE_TOOLS=ON"
        $cmakeArgs += "-DJPEGLI_ENABLE_DEVTOOLS=ON"
        $cmakeArgs += "-DJPEGLI_ENABLE_BENCHMARK=OFF"
        $cmakeArgs += "-DJPEGLI_ENABLE_FUZZERS=OFF"
        $cmakeArgs += "-DJPEGLI_ENABLE_JNI=OFF"
        Write-Host "[CONFIG] Standard: cjpegli + djpegli + ssimulacra2" -ForegroundColor Yellow
    }

    "Full" {
        $cmakeArgs += "-DJPEGLI_ENABLE_TOOLS=ON"
        $cmakeArgs += "-DJPEGLI_ENABLE_DEVTOOLS=ON"
        $cmakeArgs += "-DJPEGLI_ENABLE_BENCHMARK=ON"
        $cmakeArgs += "-DJPEGLI_ENABLE_FUZZERS=OFF"
        $cmakeArgs += "-DJPEGLI_ENABLE_JNI=ON"
        Write-Host "[CONFIG] Full: 所有组件" -ForegroundColor Yellow
    }

    "Debug" {
        $cmakeArgs += "-DJPEGLI_ENABLE_TOOLS=ON"
        $cmakeArgs += "-DJPEGLI_ENABLE_DEVTOOLS=ON"
        $cmakeArgs += "-DJPEGLI_ENABLE_BENCHMARK=OFF"
        $cmakeArgs += "-DJPEGLI_ENABLE_FUZZERS=OFF"
        Write-Host "[CONFIG] Debug: 调试模式" -ForegroundColor Yellow
    }
}

# ── CMake 配置 ────────────────────────────────────────────────────────
Write-Host "[STEP] CMake 配置中..." -ForegroundColor Cyan
Write-Host "  cmake $($cmakeArgs -join ' ')" -ForegroundColor Gray

$configResult = & cmake @cmakeArgs 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] CMake 配置失败:" -ForegroundColor Red
    $configResult | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Pop-Location
    exit 1
}
Write-Host "[OK] CMake 配置完成" -ForegroundColor Green

# ── 构建 ──────────────────────────────────────────────────────────────
Write-Host "[STEP] 编译中..." -ForegroundColor Cyan

$ninjaTargets = switch ($Target) {
    "Minimal" { @("cjpegli", "djpegli") }
    "Standard" { @("cjpegli", "djpegli", "ssimulacra2") }
    "Full" { @() }   # 空 = 全部编译
    "Debug" { @("cjpegli", "djpegli", "ssimulacra2") }
}

$buildStart = Get-Date

if ($ninjaTargets.Count -gt 0) {
    foreach ($t in $ninjaTargets) {
        Write-Host "  → ninja $t" -ForegroundColor Gray
        & ninja $t 2>&1 | ForEach-Object {
            if ($_ -match "FAILED") { Write-Host "    $_" -ForegroundColor Red }
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] $t 编译失败" -ForegroundColor Red
            Pop-Location
            exit 1
        }
        Write-Host "  ✓ $t 编译完成" -ForegroundColor Green
    }
} else {
    & ninja -j $UseJobs 2>&1 | ForEach-Object {
        if ($_ -match "FAILED") { Write-Host "    $_" -ForegroundColor Red }
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] 编译失败" -ForegroundColor Red
        Pop-Location
        exit 1
    }
}

$buildElapsed = (Get-Date) - $buildStart
Write-Host "[OK] 编译完成 (耗时: $($buildElapsed.TotalSeconds.ToString('F1'))s)" -ForegroundColor Green

# ── 安装 ──────────────────────────────────────────────────────────────
if ($InstallPfx) {
    Write-Host "[STEP] 安装到: $InstallPfx" -ForegroundColor Cyan
    & cmake --install . --prefix "$InstallPfx" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] 安装完成" -ForegroundColor Green
    } else {
        Write-Host "[WARN] 安装失败" -ForegroundColor Yellow
    }
}

# ── 验证产物 ──────────────────────────────────────────────────────────
Write-Host "[STEP] 验证构建产物..." -ForegroundColor Cyan
$tools = @("tools/cjpegli.exe", "tools/djpegli.exe")
if ($Target -ne "Minimal") { $tools += "tools/ssimulacra2.exe" }

$found = $true
foreach ($t in $tools) {
    $fullPath = "$BuildDir/$t"
    if (Test-Path $fullPath) {
        $size = (Get-Item $fullPath).Length
        Write-Host "  ✓ $t ($([math]::Round($size/1KB)) KB)" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $t (未找到)" -ForegroundColor Red
        $found = $false
    }
}

if (-not $found) {
    Write-Host "[WARN] 部分工具未生成，请检查错误日志" -ForegroundColor Yellow
}

Pop-Location

# ── 运行说明 ──────────────────────────────────────────────────────────
Write-Host @"

╔══════════════════════════════════════════════════════╗
║  构建完成！                                          ║
╠══════════════════════════════════════════════════════╣
║  工具目录: $BuildDir\tools\
║  运行测试: python compare_jpeg.py --quick
║  查看文档: type BUILD_GUIDE.md
╚══════════════════════════════════════════════════════╝
"@ -ForegroundColor Green
