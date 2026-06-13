# JPEG Compression Benchmark: JPEGLI vs MOZJPEG

> 系统性对比测试 Google JPEGLI 与 Mozilla MOZJPEG 的 JPEG 压缩效果

---

## 项目概述

本项目提供了一套完整的 JPEG 压缩器对比测试框架，包含：

- **对比测试工具** — 多进程并发的自动化测试程序，支持多维度指标采集
- **预编译工具集** — 已编译好的 `cjpegli`、`cjpeg` 及质量评估工具 `ssimulacra2`
- **构建脚本** — 一键式 PowerShell 构建脚本，支持多种构建档次
- **测试数据集** — 428 张 4K 壁纸图像（3840×2160），覆盖多种内容类型
- **完整文档** — 编译指南、跨平台编译指南、测试方法说明

## 目录结构

```
jpeg-compare/
├── README.md              # 本文件 — 项目说明
├── LICENSE                # BSD 许可证
├── PATENTS                # 专利声明
├── CHANGELOG.md           # 变更日志
├── manifest.md            # 文件清单
│
├── docs/                  # 文档
│   ├── BUILD_GUIDE.md     # 🔥 编译完整指南（含踩坑记录）
│   ├── CROSS_PLATFORM_GUIDE.md  # 🔥 跨平台编译指南（Win/Mac/iOS/Android）
│   ├── jpegli/BUILDING.md  # JPEGLI 官方编译说明
│   └── mozjpeg/BUILDING.md # MOZJPEG 官方编译说明
│
├── src/                   # 源代码
│   ├── compare_jpeg.py    # 🔥 核心：对比测试工具 v2.0
│   ├── download_wallpapers.py  # 壁纸下载工具
│   ├── CMakeLists.txt     # JPEGLI CMake 配置（参考）
│   └── scripts/
│       ├── build_jpegli.ps1   # JPEGLI 一键构建脚本
│       └── build_mozjpeg.ps1  # MOZJPEG 一键构建脚本
│
├── tools/                 # 预编译二进制
│   ├── jpegli/            # JPEGLI 工具集 + 运行时 DLL
│   │   ├── cjpegli.exe    # JPEGLI 编码器
│   │   ├── djpegli.exe    # JPEGLI 解码器
│   │   ├── ssimulacra2.exe # SSIMULACRA2 质量评分工具
│   │   └── *.dll          # 运行时依赖库
│   └── mozjpeg/           # MOZJPEG 工具集
│       ├── cjpeg.exe      # MOZJPEG 编码器
│       ├── djpeg.exe      # MOZJPEG 解码器
│       └── jpegtran.exe   # JPEG 无损变换
│
├── data/                  # 测试数据集
│   └── wallpapers/        # 4K 壁纸图像（见下方说明）
│
└── results/               # 测试结果输出目录
```

## 快速开始

### 前置条件

- **Python** 3.10+（需要 `numpy`, `Pillow` 包）
- **操作系统**: Windows 11（已测试）/ Linux / macOS

### 安装依赖

```bash
pip install numpy pillow
```

### 快速测试（3 张图像 × 2 个质量等级）

```powershell
cd jpeg-compare

# 运行快速测试
python src\compare_jpeg.py --quick
```

### 标准测试（10 张图像 × 3 个质量等级）

```powershell
python src\compare_jpeg.py --profile standard --max_images 10
```

### 全量测试（所有参数分类）

```powershell
python src\compare_jpeg.py --profile full --max_images 10
```

## 测试指标

| 类别 | 指标 | 说明 |
|------|------|------|
| **压缩效率** | 文件大小 / BPP | 每像素比特数 |
| **图像质量** | PSNR / SSIM / SSIMULACRA2 | 峰值信噪比 + 感知质量 |
| **编码性能** | 编码耗时 / 吞吐量 | 毫秒级响应时间 + MB/s |
| **稳定性** | 多次运行标准差 | 文件大小/PSNR/耗时稳定性 |
| **可靠性** | 成功率 / 失败计数 | 异常处理能力 |

## 测试场景

| Profile | 参数分类 | 说明 |
|---------|---------|------|
| `quick` | basic | 快速验证，~3 张图像 |
| `standard` | basic + boundary | 标准测试（默认） |
| `full` | 全部 | 全覆盖测试 |
| `stress` | stress | 重复编解码压力测试 |
| `boundary` | boundary | 极值参数边界测试 |

## 测试工具版本

| 工具 | 版本 | 构建时间 |
|------|------|---------|
| JPEGLI (cjpegli) | 031a0077 | 2026-06-13 |
| MOZJPEG (cjpeg) | 5.0.0 | 2026-06-13 |

> 详细构建方法请见 [编译指南](docs/BUILD_GUIDE.md)

## 测试数据集说明

`data/wallpapers/` 目录包含 428 张 4K (3840×2160) 壁纸图像，覆盖以下内容类型：

- 🌄 自然风景（山水、星空、森林）
- 🏎️ 汽车（保时捷、兰博基尼等）
- 🎮 游戏（FPS、RPG 等热门游戏）
- 🦸 角色（动漫、电影角色）
- 🎨 抽象艺术、渐变等

> **注意**: 壁纸文件总计约 1GB，已使用 ZIP 压缩存储。
> 使用前请解压: `unzip data/wallpapers.zip -d data/wallpapers/`

## 核心结论

基于 30 组测试（10 张图像 × 3 个质量等级）：

| 指标 | JPEGLI vs MOZJPEG |
|------|:---:|
| **文件大小** | **小 4.2%** |
| **PSNR** | 基本持平 (-0.00 dB) |
| **SSIMULACRA2** | 略低 0.24 分 |
| **编码速度** | 快 3-4 倍 |

## 许可证

本项目基于 BSD 3-Clause 许可证发布。

- **JPEGLI (libjxl)**: BSD 3-Clause - [LICENSE](LICENSE)
- **MOZJPEG (libjpeg-turbo)**: 基于 IJG 许可证的 BSD-like 许可证
- **本项目代码**: BSD 3-Clause

---

*Generated: 2026-06-13 | [提交 Issue](https://github.com/your-username/jpeg-compare/issues)*
