# 文件清单 — JPEG Compression Benchmark

> 生成日期: 2026-06-13
> 项目根目录: `jpeg-compare/`
> 总大小: ~1,019 MB (含测试数据集)

---

## 目录结构总览

```
jpeg-compare/
├── 📄 根目录文件 (5 个, ~10 KB)
├── 📁 docs/          (4 个, ~54 KB)
├── 📁 src/           (5 个, ~99 KB)
├── 📁 tools/         (11 个, ~2.1 MB)
├── 📁 data/          (1 个, ~964 MB)
└── 📁 results/       (空, 测试输出目录)
```

---

## 根目录文件

| 文件名 | 大小 | 用途 | 来源 |
|--------|------|------|------|
| `README.md` | 5.0 KB | **项目说明文档**（GitHub 首页），包含快速开始、测试方法、核心结论 | 本项目编写 |
| `LICENSE` | 1.5 KB | BSD 3-Clause 许可证（JPEGLI 项目原始许可证） | [jpegli](LICENSE) |
| `PATENTS` | 1.3 KB | 专利声明（JPEGLI 项目原始专利声明） | [jpegli](PATENTS) |
| `CHANGELOG.md` | 267 B | 变更日志 | [jpegli](CHANGELOG.md) |
| `README_upstream.md` | 2.5 KB | JPEGLI 上游项目的原始 README（参考） | [jpegli](README_upstream.md) |
| `.gitignore` | 548 B | Git 忽略规则配置 | 本项目编写 |

---

## docs/ — 文档

| 文件名 | 大小 | 用途 | 来源 |
|--------|------|------|------|
| `BUILD_GUIDE.md` | 24.2 KB | **🔥 编译完整指南** — JPEGLI + MOZJPEG 从零编译步骤、CMake 选项详解、11 个踩坑记录及解决方案 | 本项目编写 |
| `CROSS_PLATFORM_GUIDE.md` | 12.1 KB | **🔥 跨平台编译指南** — Windows/macOS/iOS/Android 四个平台的编译方案、toolchain 配置、踩坑记录 | 本项目编写 |
| `jpegli/BUILDING.md` | 2.4 KB | JPEGLI 官方快速编译说明 | [jpegli/BUILDING.md](https://github.com/libjxl/libjxl) |
| `mozjpeg/BUILDING.md` | 25.0 KB | MOZJPEG 官方完整编译文档（含 Windows/Linux/macOS/Android/iOS） | [mozjpeg/BUILDING.md](https://github.com/mozilla/mozjpeg) |

> **版本对应**: JPEGLI 对应 libjxl commit `031a0077`，MOZJPEG 对应 v5.0.0

---

## src/ — 源代码

| 文件名 | 大小 | 用途 | 来源 |
|--------|------|------|------|
| `compare_jpeg.py` | **46.9 KB** | **🔥 核心测试工具 v2.0** — 多进程并发架构、扩展指标体系（性能/质量/稳定性/可靠性/覆盖）、多档次参数体系（basic/boundary/stress/anomaly）、HTML/CSV/JSON 报告输出 | 本项目编写 |
| `download_wallpapers.py` | 9.5 KB | 4kwallpapers.com 批量壁纸下载器，支持多线程并发下载 | 本项目编写 |
| `CMakeLists.txt` | 19.2 KB | JPEGLI 顶层 CMake 配置（参考用，编译时需结合完整项目） | [jpegli/CMakeLists.txt](https://github.com/libjxl/libjxl) |
| `scripts/build_jpegli.ps1` | 11.3 KB | JPEGLI 一键构建脚本，支持 Minimal/Standard/Full/Debug 四种档次 | 本项目编写 |
| `scripts/build_mozjpeg.ps1` | 12.5 KB | MOZJPEG 一键构建脚本，自动检测 VS 环境与 NASM | 本项目编写 |

### compare_jpeg.py 功能特性

- **多进程并发**: 使用 `ProcessPoolExecutor` 自动利用所有 CPU 核心
- **5 个测试场景**: `quick` / `standard` / `full` / `stress` / `boundary`
- **4 类测试参数**: `basic` / `boundary` / `stress` / `anomaly`
- **14 个量化指标**: 文件大小、BPP、PSNR、SSIM、SSIMULACRA2、编码耗时、解码耗时、吞吐量、标准差等
- **3 种报告格式**: HTML（浏览器可视化）、CSV（数据分析）、JSON（程序消费）
- **自动打开报告**: 测试完成后自动在浏览器中打开 HTML 报告

---

## tools/ — 预编译工具

### tools/jpegli/ — JPEGLI 工具集

| 文件名 | 大小 | 用途 | 版本 |
|--------|------|------|------|
| `cjpegli.exe` | 651.0 KB | **JPEGLI 编码器** — 将 PNG/PPM 编码为 JPEG，支持自适应量化、XYB 色彩空间 | commit `031a0077` |
| `djpegli.exe` | 389.0 KB | **JPEGLI 解码器** — 将 JPEG 解码为 PNG/PPM/PGM 等格式 | 同上 |
| `ssimulacra2.exe` | 394.5 KB | **SSIMULACRA2 质量评分工具** — 计算两图像的感知质量差异(0-100) | 同上 |
| `jpegli_cms.dll` | 362.0 KB | JPEGLI 色彩管理模块（运行时依赖） | 同上 |
| `jpegli_threads.dll` | 20.5 KB | JPEGLI 线程支持库（运行时依赖） | 同上 |
| `zlib1.dll` | 87.5 KB | zlib 压缩库（运行时依赖, v1.3.1） | 同上 |

> **运行须知**: 执行 `ssimulacra2.exe` 时需要将 `tools/jpegli/` 目录加入 PATH（因为需要加载 DLL）。
> 测试脚本 `compare_jpeg.py` 已自动处理此问题。

### tools/mozjpeg/ — MOZJPEG 工具集

| 文件名 | 大小 | 用途 | 版本 |
|--------|------|------|------|
| `cjpeg.exe` | 102.5 KB | **MOZJPEG 编码器** — 将 PPM/BMP/TGA 编码为 JPEG | v5.0.0 |
| `djpeg.exe` | 56.0 KB | **MOZJPEG 解码器** — 将 JPEG 解码为 PPM/BMP/TGA | v5.0.0 |
| `jpegtran.exe` | 55.5 KB | **JPEG 无损变换工具** — 旋转/裁剪/无损压缩 | v5.0.0 |

> **注意**: 此构建未启用 PNG 支持（`PNG_SUPPORTED=OFF`）和 SIMD 优化（`WITH_SIMD=OFF`）。
> 如需完整功能，请参考 [编译指南](docs/BUILD_GUIDE.md) 重新编译。

---

## data/ — 测试数据集

| 文件名 | 大小 | 用途 |
|--------|------|------|
| `wallpapers.zip` | **963.9 MB** | **压缩的测试图像数据集** — 428 张 4K (3840×2160) 壁纸 |

### wallpapers.zip 说明

| 属性 | 值 |
|------|-----|
| 来源 | [4kwallpapers.com](https://4kwallpapers.com) |
| 图像数量 | 428 张 |
| 分辨率 | 3840×2160 (4K) |
| 总大小(原始) | 968 MB |
| 总大小(压缩) | 964 MB |
| 压缩格式 | ZIP (Deflate) |
| 内容类型 | 自然风景、汽车、游戏、动漫角色、抽象艺术 |

**解压方法**:

```bash
# Windows (PowerShell)
Expand-Archive -Path data/wallpapers.zip -DestinationPath data/wallpapers/

# Linux / macOS
unzip data/wallpapers.zip -d data/wallpapers/

# 或使用 7-Zip / WinRAR 等工具
```

**下载新数据集**:

```bash
python src/download_wallpapers.py --pages 20 --output data/wallpapers
```

> **注意**: 由于文件较大 (964 MB)，在 GitHub 上建议使用 [Git Large File Storage (LFS)](https://git-lfs.com/) 进行管理:
> ```bash
> git lfs track "data/wallpapers.zip"
> ```

---

## results/ — 测试结果目录

| 文件名 | 大小 | 用途 |
|--------|------|------|
| `.gitkeep` | 0 B | 占位文件，保持目录结构 |

每次运行测试后自动生成 `test_YYYYMMDD_HHMMSS/` 子目录，包含:

| 文件 | 格式 | 说明 |
|------|------|------|
| `report.html` | HTML | 汇总报告（浏览器查看） |
| `results.csv` | CSV | 详细数据（每测试用例一行） |
| `results.json` | JSON | 完整数据（含 summary） |
| `config.json` | JSON | 测试配置 |

---

## 文件大小汇总

| 目录 | 数量 | 总大小 | 说明 |
|------|:----:|:------:|------|
| 根目录 | 5 + 1 | ~11 KB | 项目元文件 + .gitignore |
| `docs/` | 5 | ~66 KB | 编译文档 |
| `src/` | 5 | ~99 KB | 源代码和构建脚本 |
| `tools/jpegli/` | 6 | ~1.9 MB | JPEGLI 预编译工具 + DLL |
| `tools/mozjpeg/` | 3 | ~214 KB | MOZJPEG 预编译工具 |
| `data/` | 1 | **~964 MB** | 🔴 测试图像数据集（ZIP 压缩） |
| `results/` | 0 | ~0 B | 测试输出目录（初始为空） |
| **总计** | **24** | **~1,019 MB** | （主要体积来自测试图像） |

---

## GitHub 上传准备

### 已就绪的文件

- ✅ `README.md` — 完整的项目说明
- ✅ `LICENSE` — BSD 3-Clause 许可证
- ✅ `PATENTS` — 专利声明
- ✅ `.gitignore` — Git 忽略规则
- ✅ `CHANGELOG.md` — 变更日志
- ✅ `manifest.md` — 本文件清单

### 大文件处理

`data/wallpapers.zip` (964 MB) 超过 100MB 阈值，建议:

**方案一: Git LFS (推荐)**

```bash
# 安装 Git LFS: https://git-lfs.com/
git lfs install
git lfs track "data/wallpapers.zip"
git add .gitattributes data/wallpapers.zip
```

**方案二: 分卷压缩**

```bash
# 将壁纸拆分为多个 50MB 的分卷
zip -s 50m data/wallpapers.zip -r data/wallpapers/
# 生成文件: wallpapers.z01, wallpapers.z02, ..., wallpapers.zip

# 解压时:
zip -s=0 data/wallpapers.zip --out data/combined.zip
unzip data/combined.zip -d data/wallpapers/
```

**方案三: 仅提供下载脚本**

```bash
# 不提交壁纸数据，用户自行下载
python src/download_wallpapers.py --pages 20 --output data/wallpapers
```

---

*清单自动生成于 2026-06-13 | [返回 README](README.md)*
