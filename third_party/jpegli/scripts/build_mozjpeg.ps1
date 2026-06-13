<#
.SYNOPSIS
    MOZJPEG 构建脚本 — 支持多种构建配置

.DESCRIPTION
    支持以下构建场景:
      - Minimal: 无 PNG/SIMD，最小依赖（本项目默认）
      - Standard: 启用 PNG 和 SIMD（需安装 libpng 和 NASM）
      - Full: 全部功能（含 TurboJPEG, Java 等）
      - Debug: 调试模式

.PARAMETER BuildType
    构建类型: Release | Debug (默认: Release)

.PARAMETER Target
    构建档次: Minimal | Standard | Full | Debug (默认: Minimal)

.PARAMETER PngDir
    libpng 安装目录 (Standard/Full 时使用)

.PARAMETER Clean
    清理之前的构建并重新编译

.PARAMETER NinjaJobs
    并行编译任务数 (默认: 自动检测 CPU 核心数)

.PARAMETER InstallPfx
    安装前缀路径 (默认: c:/mozjpeg)

.PARAMETER NoVsEnv
    跳过 VS 环境检测

.EXAMPLE
    .\scripts\build_mozjpeg.ps1 -Target Minimal
    .\scripts\build_mozjpeg.ps1 -Target Standard -PngDir "vcpkg/installed/x64-windows"
    .\scripts\build_mozjpeg.ps1 -Target Standard -Clean
#>

param(
    [ValidateSet("Release", "Debug")]
    [string]$BuildType = "Release",

    [ValidateSet("Minimal", "Standard", "Full", "Debug")]
    [string]$Target = "Minimal",

    [string]$PngDir = "",
    [switch]$Clean = $false,
    [int]$NinjaJobs = 0,
    [string]$InstallPfx = "",
    [switch]$NoVsEnv = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$ScriptDir/../mozjpeg"
$BuildDir = "$ProjectRoot/build"

# 如果是从 jpegli 项目调用，自动定位 mozjpeg
if (-not (Test-Path $ProjectRoot)) {
    $ProjectRoot = Resolve-Path "$ScriptDir/../../mozjpeg" -ErrorAction SilentlyContinue
    $BuildDir = "$ProjectRoot/build"
}
if (-not (Test-Path $ProjectRoot)) {
    Write-Host "[ERROR] 未找到 mozjpeg 项目目录！" -ForegroundColor Red
    Write-Host "  期望路径: $ProjectRoot" -ForegroundColor Red
    Write-Host "  请确保 mozjpeg 与 jpegli 在同一父目录下" -ForegroundColor Red
    exit 1
}

# ── VS 环境检测 ──────────────────────────────────────────────────────
if (-not $NoVsEnv) {
    $vsPath = "C:\Program Files\Microsoft Visual Studio\2022\Community"
    $devShellModule = "$vsPath\Common7\Tools\Microsoft.VisualStudio.DevShell.dll"
    if (Test-Path $devShellModule) {
        Import-Module $devShellModule -ErrorAction SilentlyContinue
        Enter-VsDevShell -VsInstallPath $vsPath -SkipAutomaticLocation -DevCmdArguments "-arch=x64" 2>$null
        Write-Host "[INFO] VS 2022 x64 开发环境已加载" -ForegroundColor Green
    } else {
        Write-Host "[WARN] 尝试加载 vcvars64.bat..." -ForegroundColor Yellow
        $vcvars = "$vsPath\VC\Auxiliary\Build\vcvars64.bat"
        if (Test-Path $vcvars) {
            cmd.exe /c "`"$vcvars`" && set" 2>$null | ForEach-Object {
                if ($_ -match "^(.*?)=(.*)$") { Set-Item -Path "env:$($matches[1])" -Value $matches[2] }
            }
        } else {
            Write-Host "[ERROR] 未找到 VS 环境！" -ForegroundColor Red
            exit 1
        }
    }
}

# ── 检测 NASM ────────────────────────────────────────────────────────
$hasNasm = $false
try {
    $nasmVer = & nasm --version 2>&1 | Select-Object -First 1
    if ($nasmVer -match "NASM version") {
        $hasNasm = $true
        Write-Host "[INFO] 检测到 NASM: $($nasmVer.Trim())" -ForegroundColor Green
    }
} catch { }

# ── 并行任务数 ────────────────────────────────────────────────────────
if ($NinjaJobs -le 0) {
    $NinjaJobs = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
    if (-not $NinjaJobs -or $NinjaJobs -le 0) { $NinjaJobs = 4 }
}

# ── 打印配置 ──────────────────────────────────────────────────────────
Write-Host @"

╔══════════════════════════════════════════════════════╗
║         MOZJPEG 构建脚本 v1.0                        ║
╠══════════════════════════════════════════════════════╣
║  项目目录 : $ProjectRoot
║  构建目录 : $BuildDir
║  构建类型 : $BuildType
║  构建档次 : $Target
║  NASM可用 : $hasNasm
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
    "-DCMAKE_BUILD_TYPE=$BuildType"
)

switch ($Target) {
    "Minimal" {
        $cmakeArgs += "-DPNG_SUPPORTED=OFF"
        $cmakeArgs += "-DWITH_SIMD=OFF"
        $cmakeArgs += "-DWITH_ARITH_DEC=OFF"
        $cmakeArgs += "-DWITH_ARITH_ENC=OFF"
        $cmakeArgs += "-DWITH_JAVA=OFF"
        $cmakeArgs += "-DWITH_FUZZ=OFF"
        $cmakeArgs += "-DWITH_TURBOJPEG=ON"
        Write-Host "[CONFIG] Minimal: 最小依赖，无 PNG/SIMD" -ForegroundColor Yellow
    }

    "Standard" {
        if ($hasNasm) {
            $cmakeArgs += "-DWITH_SIMD=ON"
            Write-Host "[CONFIG] SIMD: 启用 (NASM 可用)" -ForegroundColor Green
        } else {
            $cmakeArgs += "-DWITH_SIMD=OFF"
            Write-Host "[WARN] SIMD: 跳过 (未找到 NASM)" -ForegroundColor Yellow
        }

        if ($PngDir) {
            $cmakeArgs += "-DPNG_SUPPORTED=ON"
            $cmakeArgs += "-DPNG_PNG_INCLUDE_DIR=$PngDir/include"
            $cmakeArgs += "-DPNG_LIBRARY=$PngDir/lib/libpng16.dll.a"
            Write-Host "[CONFIG] PNG: 启用 (路径: $PngDir)" -ForegroundColor Green
        } else {
            $cmakeArgs += "-DPNG_SUPPORTED=OFF"
            Write-Host "[WARN] PNG: 跳过 (未指定 PngDir)" -ForegroundColor Yellow
        }

        $cmakeArgs += "-DWITH_ARITH_DEC=ON"
        $cmakeArgs += "-DWITH_ARITH_ENC=ON"
        $cmakeArgs += "-DWITH_JAVA=OFF"
        $cmakeArgs += "-DWITH_FUZZ=OFF"
        $cmakeArgs += "-DWITH_TURBOJPEG=ON"
        Write-Host "[CONFIG] Standard: 启用算术编码 + TurboJPEG" -ForegroundColor Yellow
    }

    "Full" {
        if ($PngDir) {
            $cmakeArgs += "-DPNG_SUPPORTED=ON"
            $cmakeArgs += "-DPNG_PNG_INCLUDE_DIR=$PngDir/include"
            $cmakeArgs += "-DPNG_LIBRARY=$PngDir/lib/libpng16.dll.a"
        }
        $cmakeArgs += "-DWITH_SIMD=$(if($hasNasm){'ON'}else{'OFF'})"
        $cmakeArgs += "-DWITH_ARITH_DEC=ON"
        $cmakeArgs += "-DWITH_ARITH_ENC=ON"
        $cmakeArgs += "-DWITH_JAVA=ON"
        $cmakeArgs += "-DWITH_FUZZ=OFF"
        $cmakeArgs += "-DWITH_TURBOJPEG=ON"
        Write-Host "[CONFIG] Full: 全部功能" -ForegroundColor Yellow
    }

    "Debug" {
        $cmakeArgs += "-DPNG_SUPPORTED=OFF"
        $cmakeArgs += "-DWITH_SIMD=OFF"
        $cmakeArgs += "-DWITH_ARITH_DEC=OFF"
        $cmakeArgs += "-DWITH_ARITH_ENC=OFF"
        $cmakeArgs += "-DWITH_JAVA=OFF"
        $cmakeArgs += "-DWITH_TURBOJPEG=ON"
        Write-Host "[CONFIG] Debug: 调试模式" -ForegroundColor Yellow
    }
}

# ── NASM 路径配置 ─────────────────────────────────────────────────────
if ($hasNasm) {
    $nasmPath = (Get-Command nasm).Source
    $cmakeArgs += "-DCMAKE_ASM_NASM_COMPILER=$(($nasmPath -replace '\\', '/'))"
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

$buildStart = Get-Date
& ninja -j $NinjaJobs 2>&1 | ForEach-Object {
    if ($_ -match "FAILED") { Write-Host "    $_" -ForegroundColor Red }
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 编译失败" -ForegroundColor Red
    Pop-Location
    exit 1
}

$buildElapsed = (Get-Date) - $buildStart
Write-Host "[OK] 编译完成 (耗时: $($buildElapsed.TotalSeconds.ToString('F1'))s)" -ForegroundColor Green

# ── 安装 ──────────────────────────────────────────────────────────────
$installDir = if ($InstallPfx) { $InstallPfx } else { "c:/mozjpeg" }
Write-Host "[STEP] 安装到: $installDir" -ForegroundColor Cyan
& cmake --install . --prefix "$installDir" 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] 安装完成" -ForegroundColor Green
} else {
    Write-Host "[WARN] 安装失败，但构建产物已生成" -ForegroundColor Yellow
}

# ── 验证产物 ──────────────────────────────────────────────────────────
Write-Host "[STEP] 验证构建产物..." -ForegroundColor Cyan
$tools = @(
    "cjpeg.exe", "djpeg.exe", "jpegtran.exe",
    "jpeg.dll", "turbojpeg.dll"
)

$found = $true
foreach ($t in $tools) {
    $fullPath = "$BuildDir/$t"
    if (Test-Path $fullPath) {
        $size = (Get-Item $fullPath).Length
        Write-Host "  ✓ $t ($([math]::Round($size/1KB)) KB)" -ForegroundColor Green
    } else {
        Write-Host "  - $t (可选，未生成)" -ForegroundColor Gray
    }
}

# 验证 cjpeg 可运行
try {
    $ver = & "$BuildDir/cjpeg.exe" -version 2>&1
    Write-Host "  ✓ cjpeg 版本: $($ver.Trim())" -ForegroundColor Green
} catch {
    Write-Host "  ✗ cjpeg 运行失败" -ForegroundColor Red
    $found = $false
}

Pop-Location

Write-Host @"

╔══════════════════════════════════════════════════════╗
║  构建完成！                                          ║
╠══════════════════════════════════════════════════════╣
║  工具目录: $BuildDir
║  cjpeg路径: $BuildDir\cjpeg.exe
║  使用示例: cjpeg -outfile out.jpg -quality 90 input.ppm
╚══════════════════════════════════════════════════════╝
"@ -ForegroundColor Green
