# JPEGLI & MOZJPEG 编译完整指南

> 更新时间: 2026-06-13
> 环境: Windows 11 + Visual Studio 2022 + CMake + Ninja

---

## 目录

1. [项目简介](#1-项目简介)
2. [JPEGLI (libjxl) 编译](#2-jpegli-libjxl-编译)
   - [2.1 环境要求](#21-环境要求)
   - [2.2 获取源码](#22-获取源码)
   - [2.3 CMake 配置选项详解](#23-cmake-配置选项详解)
   - [2.4 构建步骤](#24-构建步骤)
   - [2.5 构建产物](#25-构建产物)
3. [MOZJPEG 编译](#3-mozjpeg-编译)
   - [3.1 环境要求](#31-环境要求)
   - [3.2 获取源码](#32-获取源码)
   - [3.3 CMake 配置选项详解](#33-cmake-配置选项详解)
   - [3.4 构建步骤](#34-构建步骤)
   - [3.5 构建产物](#35-构建产物)
4. [踩坑记录](#4-踩坑记录)
   - [4.1 JPEGLI 踩坑](#41-jpegli-踩坑)
   - [4.2 MOZJPEG 踩坑](#42-mozjpeg-踩坑)
   - [4.3 通用踩坑](#43-通用踩坑)
5. [常用构建场景速查](#5-常用构建场景速查)
6. [构建脚本](#6-构建脚本)
   - [6.1 JPEGLI 构建脚本](#61-jpegli-构建脚本)
   - [6.2 MOZJPEG 构建脚本](#62-mozjpeg-构建脚本)
   - [6.3 使用建议](#63-使用建议)

---

## 1. 项目简介

| 项目 | 全称 | 定位 | 语言 | 编码器工具 |
|------|------|------|------|-----------|
| **JPEGLI** | libjxl 子项目 | Google 的下一代 JPEG 编码库 | C++17 | `cjpegli` |
| **MOZJPEG** | Mozilla JPEG Encoder | 基于 libjpeg-turbo 的优化编码器 | C | `cjpeg` |

两者都提供 `cjpeg` 命令行工具用于 JPEG 压缩，但底层算法和目标不同：

- **JPEGLI** 使用自适应量化、XYB 色彩空间等新技术，在同等文件大小下提供更高视觉质量
- **MOZJPEG** 优化了标准 libjpeg 的量化表、Huffman 编码，兼容性最好

---

## 2. JPEGLI (libjxl) 编译

### 2.1 环境要求

**必需:**

| 工具 | 版本要求 | 用途 |
|------|---------|------|
| CMake | >= 3.16 | 构建系统 |
| Ninja | 任意版本 | 构建工具（推荐，比 Makefile 快 2-3 倍） |
| C++17 编译器 | MSVC 2019+ / Clang 7+ / GCC 9+ | 编译 C++ 代码 |
| Git | 任意版本 | 获取源码和子模块 |

**可选:**

| 工具 | 用途 |
|------|------|
| NASM / Yasm | x86/x64 SIMD 优化（非 Windows 平台需要） |
| Doxygen | 生成 API 文档 |
| Java JDK | 构建 JNI 封装 |

**本项目使用的环境:**

- OS: Windows 11 64-bit
- Compiler: Microsoft Visual Studio 2022 Community (MSVC 19.44)
- CMake: 4.3.3
- Ninja: 随 Python 安装 (`C:\Users\User\AppData\Local\Programs\Python\Python313\Scripts\ninja.exe`)
- Python: 3.13.14

### 2.2 获取源码

```bash
# 方式一（推荐）：克隆完整仓库（含子模块）
git clone https://github.com/libjxl/libjxl.git --recursive --shallow-submodules
cd libjxl

# 方式二：如果已克隆但缺少子模块
git submodule update --init --recursive --depth 1 --recommend-shallow

# 方式三：如果下载的是 zip/tarball（不含子模块）
./deps.sh    # 手动下载第三方依赖
```

> **重要**: 子模块是必须的，它们包含 Highway SIMD 库、zlib、libpng、libjpeg-turbo 等核心依赖。缺少子模块会导致编译失败。

### 2.3 CMake 配置选项详解

#### 核心选项

| 选项 | 默认值 | 说明 |
|------|-------|------|
| `CMAKE_BUILD_TYPE` | (空) | `Release` / `Debug` / `RelWithDebInfo` |
| `BUILD_SHARED_LIBS` | OFF | 构建共享库而非静态库 |
| `JPEGLI_ENABLE_TOOLS` | ON | **构建 cjpegli/djpegli 工具** |
| `JPEGLI_ENABLE_DEVTOOLS` | OFF | 构建开发者工具（如 `ssimulacra2`） |
| `JPEGLI_ENABLE_BENCHMARK` | ON | 构建 benchmark_xl 基准测试工具 |
| `JPEGLI_ENABLE_FUZZERS` | x86_64 默认 ON | 构建模糊测试目标 |

#### 功能选项

| 选项 | 默认值 | 说明 |
|------|-------|------|
| `JPEGLI_ENABLE_JPEGLI_LIBJPEG` | ON | 构建 jpegli 版 libjpeg.so（替代系统 libjpeg） |
| `JPEGLI_ENABLE_JNI` | ON | 构建 Java JNI 封装 |
| `JPEGLI_ENABLE_SJPEG` | ON | 支持 sjpeg 编码 |
| `JPEGLI_ENABLE_OPENEXR` | ON | 支持 OpenEXR 格式 |
| `JPEGLI_ENABLE_MANPAGES` | ON | 构建 man 手册页 |
| `JPEGLI_ENABLE_DOXYGEN` | ON | 生成 Doxygen 文档 |
| `JPEGLI_TEST_TOOLS` | OFF | 运行端到端工具测试 |

#### 性能/平台选项

| 选项 | 默认值 | 说明 |
|------|-------|------|
| `JPEGLI_ENABLE_TCMALLOC` | OFF (Win) | 使用 tcmalloc 内存分配器 |
| `JPEGLI_ENABLE_LTO` | OFF | 启用 LTO 链接时优化 |
| `JPEGLI_ENABLE_SKCMS` | ON | 使用 skcms（替代 lcms2 进行色彩管理） |
| `JPEGLI_ENABLE_HWY_AVX2` | ON | 启用 AVX2 SIMD 指令集 |
| `JPEGLI_ENABLE_HWY_AVX3` | OFF | 启用 AVX-512 SIMD（需要 CPU 支持） |

#### 完整选项速查表

```bash
# 查看所有 JPEGLI 相关选项
cd build && cmake .. -LA 2>&1 | findstr JPEGLI
```

### 2.4 构建步骤

#### 方案 A：标准 Release 构建（推荐）

```powershell
# 1. 在 VS 开发者命令提示符中执行（关键！）
#    否则 MSVC 找不到标准库头文件

# 方式一：直接运行 vcvars64.bat（cmd）
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"

# 方式二：使用 VS DevShell（PowerShell）
Import-Module "C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\Microsoft.VisualStudio.DevShell.dll"
Enter-VsDevShell -VsInstallPath "C:\Program Files\Microsoft Visual Studio\2022\Community" -DevCmdArguments "-arch=x64"

# 2. 配置
cd libjxl
mkdir build && cd build
cmake .. -G Ninja `
    -DCMAKE_BUILD_TYPE=Release `
    -DBUILD_TESTING=OFF `
    -DJPEGLI_ENABLE_DEVTOOLS=OFF `
    -DJPEGLI_ENABLE_BENCHMARK=OFF `
    -DJPEGLI_ENABLE_FUZZERS=OFF

# 3. 编译
ninja -j$(nproc)          # 使用所有 CPU 核心
# 或只编译特定目标:
ninja cjpegli djpegli     # 只编译编码器/解码器
ninja ssimulacra2         # 只编译 SSIMULACRA2 工具
```

#### 方案 B：完整构建（含开发者工具和 benchmark）

```powershell
# 在 VS 开发者命令提示符中执行
cd libjxl\build
cmake .. -G Ninja `
    -DCMAKE_BUILD_TYPE=Release `
    -DBUILD_TESTING=OFF `
    -DJPEGLI_ENABLE_DEVTOOLS=ON `
    -DJPEGLI_ENABLE_BENCHMARK=ON `
    -DJPEGLI_ENABLE_TOOLS=ON

ninja
```

#### 方案 C：最小构建（仅 cjpegli/djpegli）

```powershell
cd libjxl\build
cmake .. -G Ninja `
    -DCMAKE_BUILD_TYPE=Release `
    -DBUILD_TESTING=OFF `
    -DJPEGLI_ENABLE_TOOLS=ON `
    -DJPEGLI_ENABLE_DEVTOOLS=OFF `
    -DJPEGLI_ENABLE_BENCHMARK=OFF `
    -DJPEGLI_ENABLE_FUZZERS=OFF `
    -DJPEGLI_ENABLE_JNI=OFF `
    -DJPEGLI_ENABLE_MANPAGES=OFF `
    -DJPEGLI_ENABLE_DOXYGEN=OFF `
    -DJPEGLI_ENABLE_OPENEXR=OFF `
    -DJPEGLI_ENABLE_SJPEG=OFF

ninja cjpegli djpegli
```

#### 方案 D：使用 ci.sh（仅限 Linux/macOS）

```bash
./ci.sh release                          # Release 构建
./ci.sh opt                              # RelWithDebInfo 构建
./ci.sh debug                            # Debug 构建
./ci.sh test                             # 运行测试
```

### 2.5 构建产物

构建完成后，工具位于 `build/tools/` 目录下：

| 文件 | 大小 | 说明 |
|------|------|------|
| `cjpegli.exe` | ~650 KB | JPEG 编码器（核心工具） |
| `djpegli.exe` | ~390 KB | JPEG 解码器 |
| `ssimulacra2.exe` | ~400 KB | SSIMULACRA2 质量评分工具（需 `JPEGLI_ENABLE_DEVTOOLS=ON`） |
| `benchmark_xl.exe` | - | 综合基准测试（需 `JPEGLI_ENABLE_BENCHMARK=ON`） |

运行时依赖的 DLL（在 `build/lib/` 和 `build/third_party/zlib/` 下）：

| DLL | 路径 | 说明 |
|-----|------|------|
| `jpegli_cms.dll` | `build/lib/` | 色彩管理模块（动态加载，需在 PATH 中） |
| `jpegli_threads.dll` | `build/lib/` | 线程支持（动态加载，需在 PATH 中） |
| `zlib1.dll` | `build/third_party/zlib/` | 压缩库（动态加载，需在 PATH 中） |

> **重要**: 运行 `ssimulacra2.exe` 时需要将这些 DLL 所在目录加入 PATH。测试脚本中已自动处理此问题。

---

## 3. MOZJPEG 编译

### 3.1 环境要求

| 工具 | 版本要求 | 用途 |
|------|---------|------|
| CMake | >= 2.8.12 | 构建系统 |
| C 编译器 | MSVC 2005+ / GCC 4.1+ / Clang | 编译 C 代码 |
| NASM | >= 2.13 (可选) | x86/x64 SIMD 汇编优化 |
| libpng | 任意版本 (可选) | PNG 输入支持 |

### 3.2 获取源码

```bash
# 方式一：编译最新版
git clone --depth 1 https://github.com/mozilla/mozjpeg.git
cd mozjpeg

# 方式二：通过 vcpkg 安装（Windows 推荐）
git clone https://github.com/Microsoft/vcpkg.git
cd vcpkg
.\bootstrap-vcpkg.bat
.\vcpkg integrate install
.\vcpkg install mozjpeg          # 安装预编译的 mozjpeg
```

### 3.3 CMake 配置选项详解

| 选项 | 默认值 | 说明 |
|------|-------|------|
| `CMAKE_BUILD_TYPE` | (空) | `Release` / `Debug` |
| `BUILD_SHARED_LIBS` | ON | 构建共享库 (dll/so) |
| `PNG_SUPPORTED` | ON | PNG 格式支持（需 libpng） |
| `WITH_SIMD` | ON | SIMD 加速（需 NASM/Yasm） |
| `WITH_ARITH_DEC` | OFF | 算术解码支持 |
| `WITH_ARITH_ENC` | OFF | 算术编码支持 |
| `WITH_JAVA` | OFF | Java 封装 |
| `WITH_TURBOJPEG` | ON | TurboJPEG API |
| `WITH_JPEG7` | OFF | libjpeg v7 API 兼容 |
| `WITH_JPEG8` | OFF | libjpeg v8 API 兼容 |
| `WITH_CRT_DLL` | OFF | (MSVC) 使用 CRT DLL |
| `WITH_FUZZ` | OFF | 模糊测试目标 |
| `REQUIRE_SIMD` | FALSE | 无 SIMD 时报错 |

### 3.4 构建步骤

#### 方案 A：Windows + MSVC（本项目使用）

```powershell
# 1. 设置 VS 环境
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"

# 2. 配置
cd mozjpeg
mkdir build && cd build
cmake .. -G Ninja `
    -DCMAKE_BUILD_TYPE=Release `
    -DPNG_SUPPORTED=OFF `           # 不启用 PNG 支持（简化依赖）
    -DWITH_SIMD=OFF `               # 无 NASM 时关闭 SIMD
    -DBUILD_SHARED_LIBS=ON

# 3. 编译
ninja
```

#### 方案 B：Linux/macOS 标准构建

```bash
cd mozjpeg
mkdir build && cd build
cmake -G"Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=Release \
    -DWITH_SIMD=ON \
    ..
make -j$(nproc)
sudo make install
```

#### 方案 C：启用 PNG 支持（需要 libpng）

```bash
# Linux: 先安装 libpng
sudo apt install libpng-dev

cmake .. -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DPNG_SUPPORTED=ON \            # 启用 PNG
    -DPNG_PNG_INCLUDE_DIR=/usr/include \
    -DPNG_LIBRARY=/usr/lib/x86_64-linux-gnu/libpng.so
```

### 3.5 构建产物

| 文件 | 说明 |
|------|------|
| `cjpeg.exe` | JPEG 编码器 |
| `djpeg.exe` | JPEG 解码器 |
| `jpegtran.exe` | JPEG 无损变换 |
| `tjbench.exe` | TurboJPEG 基准测试 |
| `jpeg.dll` / `jpeg.lib` | libjpeg API 共享库/导入库 |
| `turbojpeg.dll` / `turbojpeg.lib` | TurboJPEG API 共享库/导入库 |

---

## 4. 踩坑记录

### 4.1 JPEGLI 踩坑

#### 坑1：MSVC 找不到标准库头文件

**现象:**
```
fatal error C1083: 无法打开包括文件: "cstdint": No such file or directory
fatal error C1083: 无法打开包括文件: "vector": No such file or directory
```

**原因:** CMake 生成 Ninja 构建文件时，`INCLUDE` 环境变量为空（未运行 `vcvars64.bat`）。Ninja 直接调用 `cl.exe`，但 `cl.exe` 通过 `INCLUDE` 变量定位标准库头文件。

**解决方案:**

```powershell
# ❌ 错误：在普通 PowerShell 中运行 cmake
cmake .. -G Ninja                     # 生成的 build.ninja 中缺少 VC++ 包含路径
ninja ssimulacra2                     # 编译失败

# ✅ 正确：在 VS 开发者命令提示符中运行 cmake
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
cmake .. -G Ninja                     # build.ninja 包含 VC++ 标准库路径
ninja ssimulacra2                     # 编译成功

# ✅ 另一种方式：通过 cmd.exe 执行批处理
cmd.exe /c "vcvars64.bat && cmake .. -G Ninja && ninja"
```

> **注意**: 这个问题只影响**重新配置**（`cmake ..`）阶段。如果之前已经在 VS 环境中配置过，仅重新编译（`ninja`）不会出问题。只有重新运行 cmake 时才需要 VS 环境。

#### 坑2：ssimulacra2 运行时找不到 DLL

**现象:**
```
进程退出码 -1073741515 (0xC0000135) = STATUS_DLL_NOT_FOUND
```

**原因:** ssimulacra2 链接了 `jpegli_cms.dll` 和 `jpegli_threads.dll`，这些 DLL 位于 `build/lib/` 目录下，不在系统 PATH 中。

**排查过程:**

```powershell
# 1. 确认 CRT DLL 存在（不是缺少 VC 运行时）
ls C:\Windows\System32\vcruntime140.dll   # 存在

# 2. 确认构建产物中有哪些 DLL
ls build\*.dll -Recurse
# 发现: build/lib/jpegli_cms.dll
#        build/lib/jpegli_threads.dll
#        build/third_party/zlib/zlib1.dll

# 3. 将这些 DLL 目录加入 PATH 后运行
$env:Path = "build/lib;build/third_party/zlib;$env:Path"
.\build\tools\ssimulacra2.exe             # 成功！
```

**解决方案:**

```python
# Python 中运行 ssimulacra2 时正确设置环境变量
env = os.environ.copy()
env["PATH"] = ";".join(["build/lib", "build/third_party/zlib", env.get("PATH", "")])
subprocess.run(["./build/tools/ssimulacra2.exe", "a.png", "b.png"], env=env)
```

#### 坑3：ninja clean 导致全量重新编译

**现象:** 运行 `ninja -t clean ssimulacra2` 后，依赖的 Highway 库也被清理，导致后续构建需要重新编译整个 `hwy` 库（158 个目标文件）。

**原因:** `ninja -t clean ssimulacra2` 不仅清理 ssimulacra2 自身，还会清理它依赖的所有库（hwy, jpegli_gauss_blur 等）的对象文件。这不只是 `ninja clean ssimulacra2`，而是 `ninja -t clean ssimulacra2`。

**解决方案:**

```powershell
# 只清理 ssimulacra2 自身的对象文件（保留依赖库）
rm build/tools/CMakeFiles/ssimulacra2.dir/*.obj

# 只重新编译 ssimulacra2
ninja ssimulacra2                          # 不需要先 clean
```

#### 坑4：重新 cmake configure 后部分对象过时

**现象:** 修改 CMake 选项（如 `-DJPEGLI_ENABLE_DEVTOOLS=ON`）后，部分已编译的对象被标记为过时，需要重新编译。

**原因:** CMake 的 `compile_definitions` 或 `include_directories` 发生变化，Ninja 检测到依赖变化。

**解决方案:**

```powershell
# 方式一：只重建需要的目标（推荐）
ninja ssimulacra2                          # Ninja 自动处理增量编译

# 方式二：完整重建（仅当需要清理所有缓存时）
ninja clean && ninja                       # 全量重建，耗时较长
```

### 4.2 MOZJPEG 踩坑

#### 坑5：cjpeg 不支持 PNG 输入

**现象:**
```
MozJPEG can't read the image (PNG support is disabled in this build)
```

**原因:** 该项目编译的 mozjpeg 使用 `-DPNG_SUPPORTED=OFF`（因为系统未安装 libpng 开发库）。

**解决:**

```bash
# 方案一：使用 PPM 作为中间格式（推荐，最简单）
# PIL/Pillow Python 库可以轻松转换
python -c "
from PIL import Image
img = Image.open('input.png')
img.save('input.ppm', format='PPM')
"
cjpeg -outfile output.jpg input.ppm

# 方案二：安装 libpng 后重新编译（Windows 通过 vcpkg）
vcpkg install libpng:x64-windows
# 重新 cmake 时指定 PNG 库路径
cmake .. -DPNG_SUPPORTED=ON `
    -DPNG_PNG_INCLUDE_DIR="vcpkg/installed/x64-windows/include" `
    -DPNG_LIBRARY="vcpkg/installed/x64-windows/lib/libpng16.dll.a"

# 方案三：直接通过 vcpkg 安装 mozjpeg（连带 libpng 依赖）
vcpkg install mozjpeg
```

#### 坑6：Windows 下缺少 NASM 导致 SIMD 关闭

**现象:** mozjpeg 编译日志中没有 SIMD 加速信息，性能测试表明编码速度较慢。

**原因:** 系统未安装 NASM 汇编器，`WITH_SIMD=OFF`。

```powershell
# 检查是否安装了 NASM
where nasm                           # 没有输出 = 未安装

# 安装 NASM（通过 Chocolatey）
choco install nasm

# 安装后重新配置
cmake .. -DWITH_SIMD=ON
```

> **影响**: 无 SIMD 时 mozjpeg 的编码速度下降约 40-60%。但 JPEGLI 使用 Highway SIMD 库（内嵌在第三方依赖中），不受此影响。

#### 坑7：返回码 1 但实际成功

**现象:** `mozjpeg cjpeg` 返回码为 1，但输出文件正常生成。

**原因:** mozjpeg 在某些情况下（如输出警告信息）返回 1 而非 0。这是它的设计行为。

**解决方案:**

```python
# Python 中需要特殊处理
result = subprocess.run([cjpeg, ...])
if result.returncode not in (0, 1):        # 接受 0 和 1
    raise RuntimeError("编码失败")
if not output_path.exists() or output_path.stat().st_size == 0:
    raise RuntimeError("输出文件无效")
```

### 4.3 通用踩坑

#### 坑8：4K 图像 SSIM 计算极慢

**现象:** 测试脚本卡在 SSIM 计算步骤，长时间无响应。

**原因（原始代码）:** 使用 Python 双层循环实现 11x11 卷积，对 3840x2160 的图像需要约 8.3 百万次迭代，每次迭代进行 121 次乘加。
```python
# ❌ 极其缓慢的实现
for i in range(h):
    for j in range(w):
        result[i, j] = np.sum(padded[i:i+k_h, j:j+k_w] * kernel)
```

**解决方案:** 使用积分图像（Summed-Area Table / Integral Image）将 SSIM 计算时间从几分钟降至 <50ms。
```python
# ✅ 向量化实现（积分图像）
def _uniform_filter(img, size=11):
    padded = np.pad(img, size, mode="reflect")
    cs = np.cumsum(np.cumsum(padded, axis=0), axis=1)
    h, w = img.shape
    return (cs[size+pad:h+size+pad, size+pad:w+size+pad]
            - cs[pad:h+pad, size+pad:w+size+pad]
            - cs[size+pad:h+size+pad, pad:w+pad]
            + cs[pad:h+pad, pad:w+pad]) / (size*size)
```

#### 坑9：JPEG 编解码后图像尺寸变化

**现象:** 原始图像为 (2160, 3840)，JPEG 编解码后变为 (2159, 3839)。

**原因:** 某些 JPEG 编码器/解码器组合在 chroma subsampling 处理时会对尺寸进行舍入。实际上在测试中发现不是编码器的问题，而是 SSIM 函数中积分图像索引写错了（用 `size` 而非 `pad`）。

**教训:** 先确认问题来源再定位。这个坑实际上是 bug，不是 JPEG 行为。

#### 坑10：Python multiprocessing 在 Windows 上的限制

**现象:**
```
AttributeError: Can't pickle local object 'TestOrchestrator.execute.<locals>.worker'
```

**原因:** Windows 不支持 `fork()`，`multiprocessing` 使用 `spawn` 方式创建子进程。所有传递给 `ProcessPoolExecutor` 的函数必须是模块级可 pickle 的。

**解决方案:**

```python
# ❌ 错误：使用内部函数或 lambda
with ProcessPoolExecutor() as executor:
    executor.submit(lambda case: run_test(case), case)    # lambda 不可 pickle

# ✅ 正确：使用模块级函数
def run_single_test(config_dict):         # 模块级函数，可 pickle
    ...

with ProcessPoolExecutor() as executor:
    executor.submit(run_single_test, case) # 传递函数引用而非 lambda
```

#### 坑11：Manager().Value 在 Python 3.13 上的兼容性

**现象:**
```
AttributeError: 'ValueProxy' object has no attribute 'get_lock'
```

**原因:** Python 3.13 中 `multiprocessing.Manager().Value()` 返回的 proxy 对象不支持 `get_lock()`。

**解决方案:**

```python
# ❌ 旧写法
with self._progress.get_lock():
    self._progress.value += 1

# ✅ 新写法（去掉显式锁，ValueProxy 本身是线程安全的）
self._progress.value += 1
```

> **注意**: `ValueProxy` 的原子性在不同 Python 版本中有差异，对于进度计数器这种非关键数据，去掉锁是安全的。

---

## 5. 常用构建场景速查

### 场景 1：只想快速编译 cjpegli 和 djpegli

```powershell
# 本项目已编译好的工具路径:
jpegli\build\tools\cjpegli.exe
jpegli\build\tools\djpegli.exe

# 从零编译:
cd jpegli\build
cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF `
    -DJPEGLI_ENABLE_DEVTOOLS=OFF -DJPEGLI_ENABLE_BENCHMARK=OFF `
    -DJPEGLI_ENABLE_FUZZERS=OFF -DJPEGLI_ENABLE_JNI=OFF `
    -DJPEGLI_ENABLE_MANPAGES=OFF -DJPEGLI_ENABLE_DOXYGEN=OFF
ninja cjpegli djpegli
```

### 场景 2：编译含 ssimulacra2 的完整工具集

```powershell
cd jpegli\build
cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release -DJPEGLI_ENABLE_DEVTOOLS=ON
ninja cjpegli djpegli ssimulacra2
```

### 场景 3：编译 mozjpeg + PNG 支持 (Linux)

```bash
sudo apt install libpng-dev nasm
cd mozjpeg && mkdir build && cd build
cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release -DPNG_SUPPORTED=ON -DWITH_SIMD=ON
ninja
```

### 场景 4：编译 mozjpeg (Windows, 无 NASM/PNG)

```powershell
cd mozjpeg\build
cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release -DPNG_SUPPORTED=OFF -DWITH_SIMD=OFF
ninja
```

### 场景 5：完整全量测试

```powershell
cd jpegli
python compare_jpeg.py --profile full --max_images 50
```

---

## 6. 构建脚本

本项目提供了两个 PowerShell 构建脚本（位于 `scripts/` 目录下），封装了 CMake 配置和 Ninja 编译的完整流程，支持多种构建档次。

### 6.1 JPEGLI 构建脚本

**文件:** [scripts/build_jpegli.ps1](scripts/build_jpegli.ps1)

```powershell
# 最小构建 — 仅 cjpegli + djpegli（最快）
.\scripts\build_jpegli.ps1 -Target Minimal

# 标准构建 — 含 ssimulacra2（推荐）
.\scripts\build_jpegli.ps1 -Target Standard

# 全量构建 — 所有组件
.\scripts\build_jpegli.ps1 -Target Full

# 清理缓存后重新构建
.\scripts\build_jpegli.ps1 -Target Standard -Clean

# Debug 模式
.\scripts\build_jpegli.ps1 -Target Debug

# 指定安装路径
.\scripts\build_jpegli.ps1 -Target Minimal -InstallPfx "C:/jpegli"

# 跳过 VS 环境检测（已在 VS 终端中运行时）
.\scripts\build_jpegli.ps1 -Target Standard -NoVsEnv
```

**参数说明:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `-Target` | Minimal/Standard/Full/Debug | Standard | 构建档次 |
| `-BuildType` | Release/Debug/RelWithDebInfo | Release | 构建类型 |
| `-Clean` | switch | 否 | 清理缓存后重建 |
| `-NinjaJobs` | int | CPU核心数 | 并行编译任务数 |
| `-InstallPfx` | string | 空 | 安装前缀路径 |
| `-NoVsEnv` | switch | 否 | 跳过 VS 环境检测 |

**各 Target 对应的 CMake 选项:**

| Target | DEVTOOLS | BENCHMARK | TOOLS | JNI | 构建耗时 |
|--------|----------|-----------|-------|-----|---------|
| Minimal | OFF | OFF | ON | OFF | ~3 min |
| Standard | ON | OFF | ON | OFF | ~5 min |
| Full | ON | ON | ON | ON | ~8 min |
| Debug | ON | OFF | ON | OFF | ~6 min |

### 6.2 MOZJPEG 构建脚本

**文件:** [scripts/build_mozjpeg.ps1](scripts/build_mozjpeg.ps1)

```powershell
# 最小构建 — 无 PNG/SIMD（本项目默认）
.\scripts\build_mozjpeg.ps1 -Target Minimal

# 标准构建 — 启用 PNG + SIMD（需 NASM）
.\scripts\build_mozjpeg.ps1 -Target Standard -PngDir "vcpkg/installed/x64-windows"

# 全量构建 — 全部功能
.\scripts\build_mozjpeg.ps1 -Target Full -PngDir "vcpkg/installed/x64-windows"

# 清理后重建
.\scripts\build_mozjpeg.ps1 -Target Minimal -Clean
```

**参数说明:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `-Target` | Minimal/Standard/Full/Debug | Minimal | 构建档次 |
| `-BuildType` | Release/Debug | Release | 构建类型 |
| `-PngDir` | string | 空 | libpng 安装目录（Standard/Full 需要） |
| `-Clean` | switch | 否 | 清理缓存后重建 |
| `-InstallPfx` | string | c:/mozjpeg | 安装路径 |

**脚本功能特性:**

- 自动检测 VS 2022 开发环境
- 自动检测 NASM 汇编器并配置 SIMD
- 构建完成后自动验证产物完整性
- 支持增量编译（仅重新编译变化部分）
- 彩色输出，清晰显示每个步骤状态

### 6.3 使用建议

```powershell
# 首次构建 JPEGLI（标准模式，含 ssimulacra2）
.\scripts\build_jpegli.ps1 -Target Standard

# 首次构建 MOZJPEG（最小依赖模式）
.\scripts\build_mozjpeg.ps1 -Target Minimal

# 测试验证
python compare_jpeg.py --quick

# 日常开发：只重新编译修改过的源文件
.\scripts\build_jpegli.ps1 -Target Standard # Ninja 自动增量编译
```

## 附录：依赖清单

### JPEGLI 第三方依赖（git submodules）

```
third_party/
├── googletest/       # v1.16.0 - 单元测试框架
├── highway/          # HEAD - SIMD 指令集抽象层
├── skcms/            # HEAD - 色彩管理 (Google)
├── sjpeg/            # HEAD - 简单 JPEG 编码器
├── zlib/             # v1.3.1 - 压缩库
├── libpng/           # v1.6.47 - PNG 读写库
├── libjpeg-turbo/    # v2.1.5.1 - 兼容层
├── lcms/             # 可选 - 色彩管理 (替代 skcms)
└── apngdis/          # APNG 解析
```

### MOZJPEG 依赖

- **必需**: C 编译器, CMake
- **可选**: libpng, NASM/Yasm, Java JDK

---

> 本文档基于实际编译经验编写。如有问题，建议查看各项目官方的 `BUILDING.md` 和 CMakeLists.txt 获取最新信息。
