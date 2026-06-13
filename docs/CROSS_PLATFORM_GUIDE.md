# JPEGLI 跨平台编译指南

> 如何为 **Windows / macOS / iOS / Android** 四个平台编译 JPEGLI (cjpegli)

---

## 目录

1. [跨平台能力总览](#1-跨平台能力总览)
2. [平台编译方案速查](#2-平台编译方案速查)
3. [Windows 编译](#3-windows-编译)
4. [macOS 编译](#4-macos-编译)
5. [iOS 交叉编译](#5-ios-交叉编译)
6. [Android 交叉编译](#6-android-交叉编译)
7. [编译产物对照表](#7-编译产物对照表)
8. [踩坑记录](#8-踩坑记录)

---

## 1. 跨平台能力总览

### JPEGLI 跨平台支持矩阵

| 平台 | 支持状态 | 推荐编译器 | 构建方式 | 官方文档 |
|------|---------|-----------|---------|---------|
| **Windows** | ✅ 完整支持 | Clang (MSVC 不支持) | vcpkg / MSYS2 / 本地 | 有完善文档 |
| **macOS** | ✅ 完整支持 | Clang (Xcode) | ci.sh / 本地 CMake | 有完善文档 |
| **iOS** | ⚠️ 社区方案 | Clang (Xcode toolchain) | 自定义 toolchain | 无官方文档 |
| **Android** | ⚠️ 部分支持 | Clang (NDK) | Crossroad / NDK toolchain | 仅基础 CMake 集成 |

### 关键依赖说明

JPEGLI 的核心架构使其天然具备跨平台潜力：

- **语言**: C++17（所有主流编译器均支持）
- **SIMD 抽象层**: [Highway](https://github.com/google/highway) 库——支持 x86 (SSE2~AVX10.2)、ARM (NEON~SVE2)、RISC-V (RVV)、PowerPC、WASM。**一个代码库覆盖所有平台 SIMD**
- **色彩管理**: skcms（Google 的轻量色彩管理库，纯 C++11，无平台依赖）
- **压缩库**: zlib（最广泛移植的 C 库之一）

---

## 2. 平台编译方案速查

```bash
# ─── Windows ─── 方案A: vcpkg + Clang ───
# 要求: Visual Studio 2019+, vcpkg
vcpkg install gtest:x64-windows libpng:x64-windows zlib:x64-windows
cmake .. -G Ninja -DCMAKE_TOOLCHAIN_FILE=.../vcpkg.cmake \
    -DVCPKG_TARGET_TRIPLET=x64-windows -DJPEGLI_ENABLE_TCMALLOC=OFF

# ─── Windows ─── 方案B: MSYS2 MINGW64 ───
# 要求: MSYS2, mingw-w64 工具链
pacman -S mingw-w64-x86_64-toolchain mingw-w64-x86_64-cmake ninja
cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release
ninja cjpegli djpegli

# ─── macOS ───
# 要求: Xcode Command Line Tools
brew install cmake ninja
export CC=clang CXX=clang++
cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release
ninja cjpegli djpegli

# ─── iOS ───
# 要求: Xcode, 自定义 toolchain
cmake .. -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=ios-toolchain.cmake \
    -DCMAKE_OSX_SYSROOT=$(xcrun --sdk iphoneos --show-sdk-path) \
    -DCMAKE_OSX_ARCHITECTURES=arm64
ninja cjpegli

# ─── Android (ARM64) ───
# 要求: Android NDK
cmake .. -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=$NDK/build/cmake/android.toolchain.cmake \
    -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-24
ninja cjpegli
```

---

## 3. Windows 编译

### 3.1 方案 A: vcpkg + Clang（推荐）

这是官方推荐的 Windows 方案。**关键约束: 必须使用 Clang 编译器，MSVC 不支持。**

#### 步骤

```powershell
# 1. 安装 vcpkg
git clone https://github.com/Microsoft/vcpkg.git
cd vcpkg
.\bootstrap-vcpkg.bat
.\vcpkg integrate install

# 2. 安装依赖
.\vcpkg install gtest:x64-windows
.\vcpkg install giflib:x64-windows
.\vcpkg install libjpeg-turbo:x64-windows
.\vcpkg install libpng:x64-windows
.\vcpkg install zlib:x64-windows

# 3. 配置（VS 开发者命令提示符中执行）
cd libjxl
mkdir build && cd build
cmake .. -G Ninja `
    -DCMAKE_BUILD_TYPE=MinSizeRel `
    -DCMAKE_TOOLCHAIN_FILE="C:/vcpkg/scripts/buildsystems/vcpkg.cmake" `
    -DVCPKG_TARGET_TRIPLET=x64-windows `
    -DJPEGLI_ENABLE_TCMALLOC=OFF `
    -DJPEGLI_ENABLE_FUZZERS=OFF `
    -DJPEGLI_ENABLE_DEVTOOLS=ON

# 4. 编译
ninja cjpegli djpegli ssimulacra2
```

#### 使用 Visual Studio IDE

打开 CMakeLists.txt → 右键 CMakeLists.txt → CMake Settings → 添加 `x64-Clang` 配置 → 修改 CMakeSettings.json：

```json
{
  "configurations": [
    {
      "name": "x64-Clang-Release",
      "generator": "Ninja",
      "configurationType": "MinSizeRel",
      "cmakeCommandArgs": "-DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake",
      "inheritEnvironments": [ "clang_cl_x64" ],
      "variables": [
        { "name": "VCPKG_TARGET_TRIPLET", "value": "x64-windows" },
        { "name": "JPEGLI_ENABLE_TCMALLOC", "value": "False" },
        { "name": "JPEGLI_ENABLE_FUZZERS", "value": "False" }
      ]
    }
  ]
}
```

按 `F7` 构建，产物输出到 `out/build/x64-Clang-Release/tools/`。

### 3.2 方案 B: MSYS2 MINGW64

如果你更习惯 Unix-like 环境，MSYS2 是另一个选择。

```bash
# 1. 安装 MSYS2 (https://www.msys2.org/)

# 2. 在 MSYS 环境中安装依赖
pacman -Syu
pacman -S mingw-w64-x86_64-toolchain
pacman -S mingw-w64-x86_64-cmake
pacman -S mingw-w64-x86_64-ninja
pacman -S mingw-w64-x86_64-gtest

# 3. 重启 MINGW64 终端，编译
cd libjxl
mkdir build && cd build
cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release
ninja cjpegli djpegli
```

### 3.3 方案 C: 本地 Clang 编译（本项目使用）

不需要 MSYS2 或 vcpkg，直接使用 VS 自带的 Clang 工具链。

```powershell
# 在 VS 开发者命令提示符中执行
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"

cd libjxl\build
cmake .. -G Ninja `
    -DCMAKE_BUILD_TYPE=Release `
    -DBUILD_TESTING=OFF `
    -DJPEGLI_ENABLE_DEVTOOLS=ON `
    -DJPEGLI_ENABLE_BENCHMARK=OFF `
    -DJPEGLI_ENABLE_FUZZERS=OFF

ninja cjpegli djpegli ssimulacra2
```

> **注意**: 虽然 MSVC 编译器本身不被官方支持，但我们实验发现 **使用 MSVC 工具链也可以成功编译**。这不推荐用于生产，但验证了兼容性。

---

## 4. macOS 编译

### 4.1 环境准备

```bash
# 1. 安装 Xcode Command Line Tools
xcode-select --install

# 2. 安装 CMake 和 Ninja（通过 Homebrew）
brew install cmake ninja

# 3. 获取源码
git clone https://github.com/libjxl/libjxl.git --recursive --shallow-submodules
cd libjxl
```

### 4.2 标准构建

```bash
# 使用 Clang 编译
export CC=clang CXX=clang++

mkdir build && cd build
cmake .. -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_TESTING=OFF \
    -DJPEGLI_ENABLE_DEVTOOLS=ON

ninja -j$(sysctl -n hw.logicalcpu)
```

### 4.3 使用 ci.sh

```bash
./ci.sh release           # Release 构建
# 或
./ci.sh opt               # RelWithDebInfo 构建
```

### 4.4 编译产物

```
build/tools/
├── cjpegli                # JPEGLI 编码器
├── djpegli                # JPEGLI 解码器
└── ssimulacra2            # SSIMULACRA2 质量评分工具
```

---

## 5. iOS 交叉编译

JPEGLI 官方没有 iOS 的交叉编译文档，但可以通过自定义 CMake toolchain 实现。原理是用 Xcode 的 iOS SDK 配合 Clang 编译静态库。

### 5.1 方案：自定义 CMake Toolchain

创建 `ios-toolchain.cmake`：

```cmake
# ios-toolchain.cmake
set(CMAKE_SYSTEM_NAME Darwin)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(CMAKE_C_COMPILER /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang)
set(CMAKE_CXX_COMPILER /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang++)

set(CMAKE_OSX_SYSROOT /Applications/Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS.sdk)
set(CMAKE_OSX_ARCHITECTURES arm64)

set(CMAKE_C_FLAGS "-miphoneos-version-min=12.0 -fembed-bitcode")
set(CMAKE_CXX_FLAGS "-miphoneos-version-min=12.0 -fembed-bitcode -stdlib=libc++")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
```

### 5.2 编译步骤

```bash
# 1. 确认 iOS SDK 路径
xcrun --sdk iphoneos --show-sdk-path
# 输出: /Applications/Xcode.app/.../iPhoneOS.sdk

# 2. 配置（只编译静态库，不编译工具）
cd libjxl
mkdir build-ios && cd build-ios

cmake .. -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=../ios-toolchain.cmake \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_TESTING=OFF \
    -DJPEGLI_ENABLE_TOOLS=OFF \
    -DJPEGLI_ENABLE_DEVTOOLS=OFF \
    -DJPEGLI_ENABLE_BENCHMARK=OFF \
    -DJPEGLI_ENABLE_FUZZERS=OFF \
    -DJPEGLI_BUILD_STATIC_LIBS=ON \
    -DBUILD_SHARED_LIBS=OFF

# 3. 编译（只编译库，不需要 exe 工具）
ninja jpegli-static

# 4. 产物
# build-ios/lib/libjpegli.a  ← 静态库，可链接到 iOS 应用
```

### 5.3 集成到 Xcode 项目

```bash
# 将静态库和头文件复制到 Xcode 项目
cp build-ios/lib/libjpegli.a /path/to/ios-project/Libraries/
cp -r lib/include/jpegli /path/to/ios-project/Headers/

# Xcode Build Settings:
#   Other Linker Flags: -ljpegli -lz
#   Header Search Paths: $(SRCROOT)/Headers
```

### 5.4 iOS 模拟器编译

```cmake
# 只需修改 CMAKE_OSX_SYSROOT
set(CMAKE_OSX_SYSROOT /Applications/Xcode.app/Contents/Developer/Platforms/iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator.sdk)

# 或使用 xcrun 自动获取路径
set(CMAKE_OSX_SYSROOT "$(shell xcrun --sdk iphonesimulator --show-sdk-path)")
```

---

## 6. Android 交叉编译

JPEGLI 的 CMake 中已有 Android 支持代码（链接 `liblog`），但缺少完整的编译文档。

### 6.1 方案：使用 Android NDK

#### 前置条件

```bash
# 1. 下载 Android NDK (r23 或更新)
# https://developer.android.com/ndk/downloads
export NDK=/path/to/android-ndk-r27

# 2. 或者通过 SDK Manager 安装
# sdkmanager "ndk;27.0.12077973"
```

#### ARM64 (arm64-v8a)

```bash
cd libjxl
mkdir build-android-arm64 && cd build-android-arm64

cmake .. -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_TOOLCHAIN_FILE=$NDK/build/cmake/android.toolchain.cmake \
    -DANDROID_ABI=arm64-v8a \
    -DANDROID_PLATFORM=android-24 \
    -DANDROID_STL=c++_shared \
    -DBUILD_TESTING=OFF \
    -DJPEGLI_ENABLE_TOOLS=ON \
    -DJPEGLI_ENABLE_DEVTOOLS=OFF \
    -DJPEGLI_ENABLE_FUZZERS=OFF \
    -DJPEGLI_ENABLE_JNI=OFF \
    -DJPEGLI_ENABLE_BENCHMARK=OFF

ninja cjpegli djpegli

# 产物: build-android-arm64/tools/cjpegli (ELF 64-bit ARM)
```

#### ARM32 (armeabi-v7a)

```bash
mkdir build-android-arm32 && cd build-android-arm32

cmake .. -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=$NDK/build/cmake/android.toolchain.cmake \
    -DANDROID_ABI=armeabi-v7a \
    -DANDROID_PLATFORM=android-21 \
    -DANDROID_STL=c++_shared \
    -DANDROID_ARM_MODE=arm \
    -DBUILD_TESTING=OFF \
    -DJPEGLI_ENABLE_TOOLS=ON \
    -DJPEGLI_ENABLE_DEVTOOLS=OFF \
    -DJPEGLI_ENABLE_FUZZERS=OFF

ninja cjpegli djpegli
```

#### x86_64 (Android 模拟器)

```bash
mkdir build-android-x64 && cd build-android-x64

cmake .. -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=$NDK/build/cmake/android.toolchain.cmake \
    -DANDROID_ABI=x86_64 \
    -DANDROID_PLATFORM=android-24 \
    -DANDROID_STL=c++_shared \
    -DBUILD_TESTING=OFF \
    -DJPEGLI_ENABLE_TOOLS=ON \
    -DJPEGLI_ENABLE_DEVTOOLS=OFF

ninja cjpegli djpegli
```

### 6.2 方案：使用 Crossroad（Linux 上交叉编译）

```bash
# 1. 安装 Crossroad
pip3 install crossroad

# 2. 配置 Android ARM64 交叉编译环境
crossroad verify android-arm64

# 3. 编译（ci.sh 不可用，必须直接调 cmake）
crossroad w64 android-arm64
cmake .. -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_TESTING=OFF \
    -DJPEGLI_ENABLE_TOOLS=ON \
    -DJPEGLI_ENABLE_FUZZERS=OFF
ninja cjpegli
```

### 6.3 集成到 Android 应用

```gradle
// app/build.gradle
android {
    defaultConfig {
        ndk {
            abiFilters "arm64-v8a", "armeabi-v7a"
        }
    }
}

// 将 libjpegli.a 放入 app/src/main/jniLibs/{abi}/
// 或通过 CMake 集成:
//   target_link_libraries(your-native-lib ${CMAKE_SOURCE_DIR}/libs/${ANDROID_ABI}/libjpegli.a)
```

---

## 7. 编译产物对照表

| 平台 | 编码器 | 解码器 | 质量工具 | 库类型 | 备注 |
|------|--------|--------|---------|--------|------|
| **Windows x64** | `cjpegli.exe` | `djpegli.exe` | `ssimulacra2.exe` | `.dll` (动态) | 需要 VC 运行时 |
| **macOS x64** | `cjpegli` | `djpegli` | `ssimulacra2` | `.dylib` / `.a` | 通用二进制可含 arm64 |
| **macOS ARM** | `cjpegli` | `djpegli` | `ssimulacra2` | `.dylib` / `.a` | Apple Silicon 原生 |
| **iOS arm64** | ❌ (无 CLI) | ❌ (无 CLI) | ❌ | `libjpegli.a` | 静态库，嵌入 App |
| **iOS 模拟器** | ❌ (无 CLI) | ❌ (无 CLI) | ❌ | `libjpegli.a` | x86_64 或 arm64 |
| **Android ARM64** | `cjpegli` | `djpegli` | ❌ | `libjpegli.so` / `.a` | ELF 格式 |
| **Android ARM32** | `cjpegli` | `djpegli` | ❌ | `libjpegli.so` / `.a` | ELF 格式，armeabi-v7a |
| **Android x86_64** | `cjpegli` | `djpegli` | ❌ | `libjpegli.so` / `.a` | 模拟器用 |
| **WASM** | `cjpegli.wasm` | `djpegli.wasm` | ❌ | `.wasm` | 浏览器端 |

---

## 8. 踩坑记录

### 坑1：Windows 上 MSVC 编译器不被官方支持

**现象**: 官方文档明确说 "the MSVC compiler is currently not supported"。

**原因**: JPEGLI 使用了一些 MSVC 不支持或兼容性差的 C++17 特性和编译标志（如 `-fno-rtti`、特定的 `-W*` 警告标志）。

**解决方案**: 必须使用 Clang 编译器。在 Windows 上有两种方式获取：
- vs vcpkg 方案：选择 `x64-Clang` 配置
- VS 默认安装即含 Clang：`C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\Llvm\bin\clang-cl.exe`

> **注意**: 我们实验发现 MSVC 实际上可以编译大部分代码，但没有官方支持，不推荐生产使用。

### 坑2：iOS 编译无官方支持

**问题**: JPEGLI 项目没有提供 iOS 的 toolchain 或编译指南。

**原因**: JPEGLI 是 libjxl 的子项目，libjxl 主要定位为桌面/服务端库。

**解决方案**: 
- 使用上述自定义 toolchain 方案编译静态库
- Highway 库完全支持 ARM NEON/SVE，iOS 性能有保障
- 需要注意：cjpegli/djpegli 是 CLI 工具，iOS 上不能直接运行，只能链接 `libjpegli` 库后通过 API 调用

### 坑3：Android NDK 版本兼容性

**现象**: 使用过旧的 NDK 版本（r21 以下）会导致 C++17 特性编译失败。

**解决方案**: 
```bash
# 推荐 NDK 版本
# r23+ 使用 LLVM's libc++ 作为默认 STL
# r25+ 完全支持 C++17
export NDK_VERSION=27.0.12077973
```

### 坑4：Android 上需要 liblog

**现象**: 运行时日志输出需要 Android 的 `liblog` 库。

**解决方案**: CMake 已自动处理：
```cmake
# lib/CMakeLists.txt 中：
if(CMAKE_SYSTEM_NAME STREQUAL "Android")
    find_library(log-lib log)
    target_link_libraries(jpegli_base INTERFACE ${log-lib})
endif()
```

### 坑5：跨平台 Highway SIMD 目标选择

**问题**: Highway 默认启用所有 SIMD 目标，交叉编译时某些目标可能不可用。

**解决方案**:

```bash
# 交叉编译时显式禁用不支持的 SIMD 目标
cmake .. -DJPEGLI_ENABLE_HWY_AVX3=OFF \
         -DJPEGLI_ENABLE_HWY_AVX3_DL=OFF \
         -DJPEGLI_ENABLE_HWY_SSE4=OFF \
         -DJPEGLI_ENABLE_HWY_SSE2=OFF \
         -DJPEGLI_ENABLE_HWY_NEON=ON \
         -DJPEGLI_ENABLE_HWY_NEON_BF16=ON

# 或设置 HWY 基线（只编译目标架构的原生指令）
-DHWY_BASELINE_TARGETS=HWY_NEON
```

### 坑6：Android/iOS 上禁用工具编译

```bash
# 移动端不需要 CLI 工具
cmake .. -DJPEGLI_ENABLE_TOOLS=OFF    # 不编译 cjpegli/djpegli
         -DJPEGLI_ENABLE_DEVTOOLS=OFF # 不编译 ssimulacra2
         -DBUILD_TESTING=OFF          # 不编译测试
```

### 坑7：macOS 通用二进制 (Universal Binary)

```bash
# 同时编译 x86_64 + arm64 的通用二进制
cmake .. -DCMAKE_OSX_ARCHITECTURES="x86_64;arm64"
# 产物: file cjpegli → Mach-O universal binary with 2 architectures
```

---

## 附录：依赖清单

| 依赖 | Windows (vcpkg) | macOS (Homebrew) | iOS | Android (NDK) |
|------|----------------|-----------------|-----|---------------|
| C++17 编译器 | Clang (VS 内置) | Xcode Clang | Xcode Clang | NDK Clang |
| CMake | vcpkg 内置 | `brew install cmake` | macOS 安装 | NDK 内置 |
| Ninja | vcpkg 内置 | `brew install ninja` | macOS 安装 | NDK 可下载 |
| zlib | `vcpkg install zlib` | 系统自带 | 系统自带 | NDK 内置 |
| libpng | `vcpkg install libpng` | `brew install libpng` | ❌ 需要引入 | ❌ 需要引入 |
| gtest | `vcpkg install gtest` | `brew install googletest` | ❌ 不需测试 | ❌ 不需测试 |
| Highway | Git submodule | Git submodule | Git submodule | Git submodule |
| skcms | Git submodule | Git submodule | Git submodule | Git submodule |

---

> 文档版本: v1.0 | 更新日期: 2026-06-13
> 参考: [JPEGLI BUILDING.md](jpegli/BUILDING.md) | [Google Highway](https://github.com/google/highway)
