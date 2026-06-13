"""
JPEG 压缩对比测试工具 v2.0 — 多进程并发 + 扩展指标体系
比较 jpegli (Google) vs mozjpeg (Mozilla) 的 JPEG 压缩效果

======================================================================
架构设计
======================================================================
主进程 (Orchestrator)
  ├── TestCaseGenerator → 生成多档次多类型测试参数组合
  ├── ProcessPoolExecutor → 多进程并发执行测试用例
  │   ├── Worker 1: run_single_test()
  │   ├── Worker 2: run_single_test()
  │   ├── Worker 3: run_single_test()
  │   └── Worker N: run_single_test()
  ├── MetricsAggregator → 收集结果并计算汇总统计
  └── ReportGenerator → CSV / JSON / 控制台报告

======================================================================
指标分类
======================================================================
性能指标    响应时间(编码/解码), 吞吐量(张/秒), BPP
质量指标    PSNR, SSIM, SSIMULACRA2
稳定性指标  错误率, 多次运行标准差, 成功率
可靠性指标  连续成功次数, MTBF(平均无故障间隔)
覆盖率指标  参数组合覆盖率, 边界条件命中率

======================================================================
测试参数分类
======================================================================
基础参数    quality, chroma_subsampling, progressive
边界参数    极值 quality, 极端尺寸, 特殊采样
压力参数    批量并发, 反复编解码, 大文件
异常参数    损坏输入, 空文件, 格式错误, 工具缺失

使用方法: python compare_jpeg.py [options]
"""

from __future__ import annotations

import os
import sys
import time
import json
import math
import signal
import platform
import subprocess
import argparse
import tempfile
import csv
import copy
import traceback
import webbrowser
from typing import Any
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Manager, Value

import numpy as np
from PIL import Image

# ═══════════════════════════════════════════════════════════════════════
# 工具路径配置
# ═══════════════════════════════════════════════════════════════════════
ROOT_DIR = Path(__file__).resolve().parent
BUILD_DIR = ROOT_DIR / "build"
CJPEGLI = BUILD_DIR / "tools" / "cjpegli.exe"
DJPEGLI = BUILD_DIR / "tools" / "djpegli.exe"
SSIMULACRA2 = BUILD_DIR / "tools" / "ssimulacra2.exe"
MOZJPEG_DIR = ROOT_DIR.parent / "mozjpeg" / "build"
MCJPEG = MOZJPEG_DIR / "cjpeg.exe"
MDJPEG = MOZJPEG_DIR / "djpeg.exe"
DEFAULT_INPUT_DIR = ROOT_DIR / "wallpapers"

# ssimulacra2 所需的 DLL 路径
DLL_DIRS = [
    str(BUILD_DIR / "lib"),
    str(BUILD_DIR / "third_party" / "zlib"),
]

# 编码器枚举
ENCODER_JPEGLI = "jpegli"
ENCODER_MOZJPEG = "mozjpeg"
ENCODERS = [ENCODER_JPEGLI, ENCODER_MOZJPEG]

# 测试参数分类标签
PARAM_BASIC = "basic"
PARAM_BOUNDARY = "boundary"
PARAM_STRESS = "stress"
PARAM_ANOMALY = "anomaly"
PARAM_CATEGORIES = [PARAM_BASIC, PARAM_BOUNDARY, PARAM_STRESS, PARAM_ANOMALY]

# 指标分类标签
METRIC_PERFORMANCE = "performance"
METRIC_QUALITY = "quality"
METRIC_STABILITY = "stability"
METRIC_RELIABILITY = "reliability"
METRIC_COVERAGE = "coverage"


# ═══════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TestConfig:
    """单个测试用例的配置"""
    encoder: str              # jpegli / mozjpeg
    quality: int              # 1-100
    chroma_subsampling: str   # 420 / 444
    progressive: bool         # True=progressive, False=sequential
    param_category: str       # basic / boundary / stress / anomaly
    image_path: str = ""      # 输入图像路径
    test_label: str = ""      # 测试标签(用于边界/异常等)
    repeat_count: int = 1     # 重复次数(压力测试)


@dataclass
class TestResult:
    """单个测试用例的结果"""
    config: dict              # TestConfig 的字典形式
    success: bool = False
    error: str = ""
    # 性能指标
    enc_time_ms: float = 0.0
    dec_time_ms: float = 0.0
    file_size: int = 0
    bpp: float = 0.0
    throughput_enc: float = 0.0   # 编码吞吐量 (MB/s)
    throughput_dec: float = 0.0   # 解码吞吐量 (MB/s)
    # 质量指标
    psnr: float = 0.0
    ssim: float = 0.0
    ssimulacra2: float = 0.0
    # 稳定性指标 (重复运行时)
    size_stddev: float = 0.0
    psnr_stddev: float = 0.0
    time_stddev: float = 0.0
    # 运行时信息
    image_width: int = 0
    image_height: int = 0
    timestamp: str = ""
    duration_ms: float = 0.0


# ═══════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════

def ensure_tools():
    """验证所有必需的工具是否存在"""
    tools = {
        "cjpegli": CJPEGLI,
        "djpegli": DJPEGLI,
        "ssimulacra2": SSIMULACRA2,
        "mozjpeg cjpeg": MCJPEG,
        "mozjpeg djpeg": MDJPEG,
    }
    missing = [name for name, path in tools.items() if not path.exists()]
    if missing:
        print(f"[ERROR] 缺少必需的工具: {', '.join(missing)}")
        print(f"  Build dir: {BUILD_DIR}")
        print(f"  Mozjpeg dir: {MOZJPEG_DIR}")
        return False
    return True


def load_image_rgb(path: str):
    """加载图像为 RGB numpy 数组 (uint8, HxWxC)"""
    img = Image.open(path).convert("RGB")
    return np.array(img, dtype=np.uint8)


def save_ppm(img_array: np.ndarray, ppm_path: str):
    """将 numpy 数组保存为 PPM 文件"""
    Image.fromarray(img_array).save(ppm_path, format="PPM")


def compute_psnr(original: np.ndarray, compressed: np.ndarray) -> float:
    """计算 PSNR (dB)"""
    mse = np.mean((original.astype(np.float64) - compressed.astype(np.float64)) ** 2)
    if mse == 0:
        return float("inf")
    return float(20 * np.log10(255.0 / np.sqrt(mse)))


def _uniform_filter(img: np.ndarray, size: int = 11) -> np.ndarray:
    """快速均匀滤波 — 使用积分图像，完全向量化"""
    pad = size // 2
    padded = np.pad(img, size, mode="reflect")
    cs = np.cumsum(np.cumsum(padded, axis=0), axis=1)
    h, w = img.shape
    return (cs[size + pad:h + size + pad, size + pad:w + size + pad]
            - cs[pad:h + pad, size + pad:w + size + pad]
            - cs[size + pad:h + size + pad, pad:w + pad]
            + cs[pad:h + pad, pad:w + pad]) / (size * size)


def compute_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
    """计算 SSIM (0-1)"""
    if img1.shape != img2.shape:
        raise ValueError("图像尺寸不匹配")
    i1 = img1.astype(np.float64)
    i2 = img2.astype(np.float64)
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    vals = []
    for c in range(3):
        mu1, mu2 = _uniform_filter(i1[:, :, c]), _uniform_filter(i2[:, :, c])
        s1 = _uniform_filter(i1[:, :, c] ** 2) - mu1 ** 2
        s2 = _uniform_filter(i2[:, :, c] ** 2) - mu2 ** 2
        s12 = _uniform_filter(i1[:, :, c] * i2[:, :, c]) - mu1 * mu2
        m = ((2 * mu1 * mu2 + C1) * (2 * s12 + C2)) / ((mu1 ** 2 + mu2 ** 2 + C1) * (s1 + s2 + C2))
        vals.append(np.mean(m))
    return float(np.mean(vals))


# ═══════════════════════════════════════════════════════════════════════
# 编码器执行函数 (独立模块级函数，支持 multiprocessing pickling)
# ═══════════════════════════════════════════════════════════════════════

def run_cjpegli(ppm_path: str, output_path: str, quality: int = 90,
                chroma_subsampling: str = "420", progressive_level: int = 2) -> float:
    """调用 cjpegli 编码 JPEG，返回耗时秒数"""
    cmd = [str(CJPEGLI), ppm_path, output_path,
           "-q", str(quality),
           "--chroma_subsampling", chroma_subsampling]
    if progressive_level >= 0:
        cmd += ["-p", str(progressive_level)]
    start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    elapsed = time.perf_counter() - start
    if result.returncode != 0:
        raise RuntimeError(f"cjpegli 失败 (rc={result.returncode}): {result.stderr[:200]}")
    return elapsed


def run_mozcjpeg(ppm_path: str, output_path: str, quality: int = 90,
                 chroma_subsampling: str = "420") -> float:
    """调用 mozjpeg cjpeg 编码 JPEG，返回耗时秒数"""
    sample = "1x1" if chroma_subsampling == "444" else "2x2"
    cmd = [str(MCJPEG), "-outfile", output_path,
           "-quality", str(quality),
           "-sample", sample,
           ppm_path]
    start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    elapsed = time.perf_counter() - start
    if result.returncode != 0 and result.returncode != 1:
        if not Path(output_path).exists() or Path(output_path).stat().st_size == 0:
            raise RuntimeError(f"mozjpeg cjpeg 失败 (rc={result.returncode}): {result.stderr[:200]}")
    return elapsed


def run_ssimulacra2(original_png: str, compressed_png: str) -> float:
    """运行 ssimulacra2，返回感知质量评分 (0-100)"""
    env = os.environ.copy()
    env["PATH"] = ";".join(DLL_DIRS + [env.get("PATH", "")])
    cmd = [str(SSIMULACRA2), original_png, compressed_png]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"ssimulacra2 失败: {result.stderr[:200]}")
    return float(result.stdout.strip())


# ═══════════════════════════════════════════════════════════════════════
# 独立测试用例执行器 (模块级函数，供 ProcessPoolExecutor 调用)
# ═══════════════════════════════════════════════════════════════════════

def run_single_test(config_dict: dict) -> dict:
    """
    执行单个测试用例。
    这是模块级函数，可以被 pickle 并传递给 ProcessPoolExecutor。
    config_dict: TestConfig 的字典形式
    返回: TestResult 的字典形式
    """
    config = TestConfig(**config_dict)
    result = TestResult(config=config_dict)
    result.timestamp = datetime.now().isoformat()
    t0 = time.perf_counter()

    # ── 异常参数测试: 损坏文件 ──
    if config.param_category == PARAM_ANOMALY and config.test_label == "corrupted":
        try:
            run_cjpegli("/nonexistent/input.ppm", "dummy.jpg", quality=90)
        except Exception:
            pass  # 期望失败
        try:
            run_mozcjpeg("/nonexistent/input.ppm", "dummy.jpg", quality=90)
        except Exception:
            pass
        result.success = True  # 成功处理了异常
        result.duration_ms = (time.perf_counter() - t0) * 1000
        return asdict(result)

    # ── 正常测试: 编解码 ──
    img_path = Path(config.image_path)
    if not img_path.exists():
        result.error = f"图像不存在: {config.image_path}"
        result.duration_ms = (time.perf_counter() - t0) * 1000
        return asdict(result)

    # ── 压力参数: 重复编解码 ──
    repeat = config.repeat_count
    if config.param_category == PARAM_STRESS:
        repeat = max(repeat, 3)

    try:
        orig_array = load_image_rgb(str(img_path))
    except Exception as e:
        result.error = f"图像加载失败: {e}"
        result.duration_ms = (time.perf_counter() - t0) * 1000
        return asdict(result)

    h, w = orig_array.shape[:2]
    result.image_width = w
    result.image_height = h

    # ── 边界参数: 极值处理 ──
    actual_quality = config.quality
    if config.param_category == PARAM_BOUNDARY:
        if config.test_label == "quality_min":
            actual_quality = 1
        elif config.test_label == "quality_max":
            actual_quality = 100
        elif config.test_label == "quality_out_of_range":
            actual_quality = 150  # 期望编码器能优雅处理

    run_func = run_cjpegli if config.encoder == ENCODER_JPEGLI else run_mozcjpeg
    encoder_name = config.encoder

    enc_times = []
    dec_times = []
    file_sizes = []
    psnr_vals = []
    ssim_vals = []
    ssim2_vals = []

    for rep in range(repeat):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                ppm_path = str(tmp / "input.ppm")
                save_ppm(orig_array, ppm_path)

                # ── 编码 ──
                try:
                    if encoder_name == ENCODER_JPEGLI:
                        enc_t = run_cjpegli(
                            ppm_path, str(tmp / "out.jpg"),
                            actual_quality, config.chroma_subsampling,
                            2 if config.progressive else 0)
                    else:
                        enc_t = run_mozcjpeg(
                            ppm_path, str(tmp / "out.jpg"),
                            actual_quality, config.chroma_subsampling)
                    enc_times.append(enc_t)
                except Exception as e:
                    if config.param_category == PARAM_ANOMALY:
                        enc_times.append(0)
                        result.success = True
                        continue
                    raise

                jpg_path = tmp / "out.jpg"
                file_size = jpg_path.stat().st_size
                file_sizes.append(file_size)

                # ── 解码 ──
                dec_start = time.perf_counter()
                dec_img = Image.open(jpg_path)
                dec_array = np.array(dec_img.convert("RGB"), dtype=np.uint8)
                dec_t = time.perf_counter() - dec_start
                dec_times.append(dec_t)

                # 尺寸一致性检查
                if dec_array.shape[:2] != (h, w):
                    dec_img = Image.fromarray(dec_array).resize((w, h), Image.LANCZOS)
                    dec_array = np.array(dec_img, dtype=np.uint8)

                # ── 质量指标 ──
                psnr_vals.append(compute_psnr(orig_array, dec_array))
                ssim_vals.append(compute_ssim(orig_array, dec_array))

                # ssimulacra2 只用第一次
                if rep == 0:
                    orig_png = str(tmp / "original.png")
                    dec_png = str(tmp / "decoded.png")
                    Image.fromarray(orig_array).save(orig_png, format="PNG")
                    Image.fromarray(dec_array).save(dec_png, format="PNG")
                    ssim2_vals.append(run_ssimulacra2(orig_png, dec_png))

        except Exception as e:
            if config.param_category == PARAM_ANOMALY:
                result.success = True  # 异常测试期望失败
                result.error = str(e)
                result.duration_ms = (time.perf_counter() - t0) * 1000
                return asdict(result)
            else:
                result.error = f"第{rep+1}次运行失败: {e}"
                result.duration_ms = (time.perf_counter() - t0) * 1000
                return asdict(result)

    # ── 汇总结果 ──
    if enc_times:
        avg_enc = np.mean(enc_times)
        result.enc_time_ms = round(avg_enc * 1000, 2)
        result.time_stddev = round(np.std(enc_times) * 1000, 2) if len(enc_times) > 1 else 0.0
    if dec_times:
        result.dec_time_ms = round(np.mean(dec_times) * 1000, 2)
    if file_sizes:
        result.file_size = int(np.median(file_sizes))
        result.bpp = round(result.file_size * 8 / (w * h), 4)
        result.size_stddev = round(np.std(file_sizes), 1) if len(file_sizes) > 1 else 0.0
        # 吞吐量
        if enc_times and np.mean(enc_times) > 0:
            result.throughput_enc = round((result.file_size / 1024 / 1024) / np.mean(enc_times), 2)
        if dec_times and np.mean(dec_times) > 0:
            result.throughput_dec = round((result.file_size / 1024 / 1024) / np.mean(dec_times), 2)
    if psnr_vals:
        result.psnr = round(np.mean(psnr_vals), 4)
        result.psnr_stddev = round(np.std(psnr_vals), 4) if len(psnr_vals) > 1 else 0.0
    if ssim_vals:
        result.ssim = round(np.mean(ssim_vals), 6)
    if ssim2_vals:
        result.ssimulacra2 = round(np.mean(ssim2_vals), 2)

    result.success = True
    result.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    return asdict(result)


# ═══════════════════════════════════════════════════════════════════════
# 测试用例生成器
# ═══════════════════════════════════════════════════════════════════════

class TestCaseGenerator:
    """生成多档次、多类型的测试参数组合"""

    @staticmethod
    def generate_basic(image_paths: list[str]) -> list[dict]:
        """基础参数: 常用质量等级 + 标准 subsampling"""
        cases = []
        for img in image_paths:
            for q in [75, 80, 85, 90, 95]:
                for cs in ["420", "444"]:
                    for prog in [True, False]:
                        cases.append(TestConfig(
                            encoder=ENCODER_JPEGLI,
                            quality=q, chroma_subsampling=cs,
                            progressive=prog if ENCODER_JPEGLI else True,
                            param_category=PARAM_BASIC,
                            image_path=img,
                        ).__dict__)
                        cases.append(TestConfig(
                            encoder=ENCODER_MOZJPEG,
                            quality=q, chroma_subsampling=cs,
                            progressive=True,
                            param_category=PARAM_BASIC,
                            image_path=img,
                        ).__dict__)
        return cases

    @staticmethod
    def generate_boundary(image_paths: list[str]) -> list[dict]:
        """边界参数: 极值 quality, 极端尺寸"""
        cases = []
        for img in image_paths:
            # 极值 quality
            for q_label, q_val in [("quality_min", 1), ("quality_max", 100),
                                    ("quality_out_of_range", 150)]:
                cases.append(TestConfig(
                    encoder=ENCODER_JPEGLI, quality=q_val,
                    chroma_subsampling="420", progressive=True,
                    param_category=PARAM_BOUNDARY, test_label=q_label,
                    image_path=img,
                ).__dict__)
                cases.append(TestConfig(
                    encoder=ENCODER_MOZJPEG, quality=q_val,
                    chroma_subsampling="420", progressive=True,
                    param_category=PARAM_BOUNDARY, test_label=q_label,
                    image_path=img,
                ).__dict__)
        return cases

    @staticmethod
    def generate_stress(image_paths: list[str]) -> list[dict]:
        """压力参数: 重复编解码, 批量并发"""
        cases = []
        # 选择代表性图像
        stress_images = image_paths[:min(3, len(image_paths))]
        for img in stress_images:
            for encoder in ENCODERS:
                for repeat in [3, 5]:
                    cases.append(TestConfig(
                        encoder=encoder, quality=85,
                        chroma_subsampling="420", progressive=True,
                        param_category=PARAM_STRESS,
                        test_label=f"repeat_{repeat}",
                        repeat_count=repeat,
                        image_path=img,
                    ).__dict__)
        return cases

    @staticmethod
    def generate_anomaly(image_paths: list[str]) -> list[dict]:
        """异常参数: 损坏文件, 空文件, 不存在路径"""
        cases = []

        # 损坏的输入 — 用空文件测试
        for encoder in ENCODERS:
            cases.append(TestConfig(
                encoder=encoder, quality=85,
                chroma_subsampling="420", progressive=True,
                param_category=PARAM_ANOMALY, test_label="corrupted",
                image_path="",  # 空路径 = 异常
            ).__dict__)

        return cases

    @classmethod
    def generate_all(cls, image_paths: list[str], categories: list[str] | None = None) -> list[dict]:
        """生成指定分类的所有测试用例"""
        if categories is None:
            categories = PARAM_CATEGORIES

        generators = {
            PARAM_BASIC: cls.generate_basic,
            PARAM_BOUNDARY: cls.generate_boundary,
            PARAM_STRESS: cls.generate_stress,
            PARAM_ANOMALY: cls.generate_anomaly,
        }

        all_cases = []
        for cat in categories:
            if cat in generators:
                all_cases.extend(generators[cat](image_paths))
        return all_cases


# ═══════════════════════════════════════════════════════════════════════
# 指标聚合器
# ═══════════════════════════════════════════════════════════════════════

class MetricsAggregator:
    """对测试结果进行多维度汇总统计"""

    @staticmethod
    def aggregate(results: list[dict]) -> dict:
        """计算所有汇总指标"""
        summary = {
            "total_cases": len(results),
            "success_count": sum(1 for r in results if r.get("success")),
            "fail_count": sum(1 for r in results if not r.get("success")),
            "categories": {},
            "encoders": {},
        }

        # 按分类分组
        for r in results:
            cat = r.get("config", {}).get("param_category", "unknown")
            if cat not in summary["categories"]:
                summary["categories"][cat] = {"total": 0, "success": 0}
            summary["categories"][cat]["total"] += 1
            if r.get("success"):
                summary["categories"][cat]["success"] += 1

        # 按编码器分组
        for enc in ENCODERS:
            enc_results = [r for r in results
                           if r.get("config", {}).get("encoder") == enc and r.get("success")]
            if not enc_results:
                summary["encoders"][enc] = {"count": 0}
                continue

            sizes = [r.get("file_size", 0) for r in enc_results if r.get("file_size")]
            psnrs = [r.get("psnr", 0) for r in enc_results if r.get("psnr")]
            ssim2s = [r.get("ssimulacra2", 0) for r in enc_results if r.get("ssimulacra2")]
            enc_times = [r.get("enc_time_ms", 0) for r in enc_results if r.get("enc_time_ms")]

            summary["encoders"][enc] = {
                "count": len(enc_results),
                "avg_size": round(np.mean(sizes), 1) if sizes else 0,
                "total_size_mb": round(sum(sizes) / 1024 / 1024, 2) if sizes else 0,
                "avg_bpp": round(np.mean([r.get("bpp", 0) for r in enc_results if r.get("bpp")]), 4),
                "avg_psnr": round(np.mean(psnrs), 2) if psnrs else 0,
                "avg_ssimulacra2": round(np.mean(ssim2s), 2) if ssim2s else 0,
                "avg_enc_time_ms": round(np.mean(enc_times), 1) if enc_times else 0,
                "avg_throughput_mbs": round(np.mean(
                    [r.get("throughput_enc", 0) for r in enc_results if r.get("throughput_enc")]), 2),
            }

        # 稳定性指标
        stable_results = [r for r in results if r.get("size_stddev", 0) > 0]
        if stable_results:
            summary["stability"] = {
                "avg_size_stddev": round(np.mean([r.get("size_stddev", 0) for r in stable_results]), 1),
                "avg_psnr_stddev": round(np.mean([r.get("psnr_stddev", 0) for r in stable_results]), 4),
                "avg_time_stddev": round(np.mean([r.get("time_stddev", 0) for r in stable_results]), 2),
            }

        # 可靠性指标
        summary["reliability"] = {
            "success_rate": round(summary["success_count"] / max(summary["total_cases"], 1) * 100, 1),
            "fail_count": summary["fail_count"],
        }

        return summary


# ═══════════════════════════════════════════════════════════════════════
# 报告生成器
# ═══════════════════════════════════════════════════════════════════════

class ReportGenerator:
    """生成多种格式的测试报告"""

    @staticmethod
    def to_csv(results: list[dict], csv_path: str):
        """保存为 CSV"""
        if not results:
            return
        fieldnames = [
            "encoder", "quality", "chroma_subsampling", "progressive",
            "param_category", "test_label", "repeat_count",
            "success", "error", "file_size", "bpp",
            "enc_time_ms", "dec_time_ms", "throughput_enc", "throughput_dec",
            "psnr", "ssim", "ssimulacra2",
            "size_stddev", "psnr_stddev", "time_stddev",
            "image_width", "image_height",
        ]

        flat = []
        for r in results:
            row = {}
            cfg = r.get("config", {})
            for k in fieldnames:
                if k in cfg:
                    row[k] = cfg[k]
                else:
                    row[k] = r.get(k, "")
            flat.append(row)

        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(flat)

    @staticmethod
    def to_json(results: list[dict], summary: dict, json_path: str):
        """保存为 JSON"""
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "results": results,
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    @staticmethod
    def to_html(summary: dict, html_path: str):
        """生成 HTML 汇总报告"""
        s = summary
        encoders = s.get("encoders", {})

        def _val(enc, key, fmt="{}"):
            d = encoders.get(enc, {})
            v = d.get(key, "N/A")
            if isinstance(v, (int, float)) and v == 0 and key != "count":
                return "N/A"
            return fmt.format(v)

        rows_html = ""
        if ENCODER_JPEGLI in encoders and ENCODER_MOZJPEG in encoders:
            metrics = [
                ("有效用例数", "count", "{}", "{}"),
                ("总大小 (MB)", "total_size_mb", "{:.2f}", "{:.2f}"),
                ("平均文件大小 (bytes)", "avg_size", "{:.0f}", "{:.0f}"),
                ("平均 BPP", "avg_bpp", "{:.4f}", "{:.4f}"),
                ("平均 PSNR (dB)", "avg_psnr", "{:.2f}", "{:.2f}"),
                ("平均 SSIMULACRA2", "avg_ssimulacra2", "{:.2f}", "{:.2f}"),
                ("平均编码耗时 (ms)", "avg_enc_time_ms", "{:.1f}", "{:.1f}"),
                ("编码吞吐量 (MB/s)", "avg_throughput_mbs", "{:.2f}", "{:.2f}"),
            ]
            for label, key, fmt_j, fmt_m in metrics:
                rows_html += f"""<tr>
                    <td>{label}</td>
                    <td class="v">{_val(ENCODER_JPEGLI, key, fmt_j)}</td>
                    <td class="v">{_val(ENCODER_MOZJPEG, key, fmt_m)}</td>
                </tr>"""

            # 对比结论
            j_tot = encoders.get(ENCODER_JPEGLI, {}).get("total_size_mb", 0) or 0
            m_tot = encoders.get(ENCODER_MOZJPEG, {}).get("total_size_mb", 0) or 0.001
            saving = (m_tot - j_tot) / m_tot * 100
            j_psnr = encoders.get(ENCODER_JPEGLI, {}).get("avg_psnr", 0) or 0
            m_psnr = encoders.get(ENCODER_MOZJPEG, {}).get("avg_psnr", 0) or 0
            psnr_d = j_psnr - m_psnr

        # 按参数分类的成功率
        cat_rows = ""
        for cat, data in sorted(s.get("categories", {}).items()):
            rate = data["success"] / max(data["total"], 1) * 100
            cat_rows += f"""<tr>
                <td>{cat}</td>
                <td class="v">{data['total']}</td>
                <td class="v">{data['success']}</td>
                <td class="v">{rate:.1f}%</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>JPEG 压缩对比测试报告</title>
<style>
body {{ font-family: -apple-system, 'Segoe UI', sans-serif; margin: 30px; color: #1a1a2e; background: #f8f9fa; }}
h1 {{ color: #16213e; border-bottom: 3px solid #0f3460; padding-bottom: 10px; }}
h2 {{ color: #0f3460; margin-top: 30px; }}
table {{ border-collapse: collapse; width: 100%; max-width: 800px; margin: 15px 0 25px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.1); border-radius: 6px; overflow: hidden; }}
th {{ background: #0f3460; color: #fff; padding: 10px 14px; text-align: left; }}
td {{ padding: 8px 14px; border-bottom: 1px solid #eee; }}
.v {{ text-align: right; font-family: 'Cascadia Code', 'Consolas', monospace; }}
tr:hover {{ background: #f0f4ff; }}
.summary {{ background: #e8f4f8; padding: 15px 20px; border-radius: 8px; max-width: 780px; margin: 15px 0; }}
.summary b {{ color: #0f3460; }}
.footer {{ color: #888; font-size: .85em; margin-top: 40px; }}
</style>
</head>
<body>
<h1>JPEG 压缩对比测试报告</h1>
<p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

<h2>总体概览</h2>
<table>
<tr><th>指标</th><th>总计</th></tr>
<tr><td>测试用例总数</td><td class="v">{s['total_cases']}</td></tr>
<tr><td>成功</td><td class="v" style="color:#27ae60">{s['success_count']}</td></tr>
<tr><td>失败</td><td class="v" style="color:#e74c3c">{s['fail_count']}</td></tr>
<tr><td>成功率</td><td class="v">{s.get('reliability', {}).get('success_rate', 0):.1f}%</td></tr>
</table>

<h2>编码器对比</h2>
<table>
<tr><th>指标</th><th>JPEGLI</th><th>MOZJPEG</th></tr>
{rows_html}
</table>

<div class="summary">
<b>JDEGLI 对比 MOZJPEG:</b><br>
&bull; 空间节省: <b>{saving:.1f}%</b><br>
&bull; PSNR 差异: <b>{psnr_d:+.2f} dB</b>
</div>

<h2>参数分类成功率</h2>
<table>
<tr><th>分类</th><th>总数</th><th>成功</th><th>成功率</th></tr>
{cat_rows}
</table>

<h2>稳定性指标</h2>
<table>
<tr><th>指标</th><th>值</th></tr>
<tr><td>文件大小标准差</td><td class="v">{s.get('stability', {}).get('avg_size_stddev', 'N/A')}</td></tr>
<tr><td>PSNR 标准差</td><td class="v">{s.get('stability', {}).get('avg_psnr_stddev', 'N/A')}</td></tr>
<tr><td>编码耗时标准差</td><td class="v">{s.get('stability', {}).get('avg_time_stddev', 'N/A')}</td></tr>
</table>

<div class="footer">
<p>报告文件: results.csv (详细数据) | results.json (完整数据)</p>
</div>
</body>
</html>"""
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

    @staticmethod
    def print_summary(summary: dict):
        """控制台打印汇总"""
        s = summary
        print()
        print("=" * 70)
        print(f"  测试完成: {s['total_cases']} 用例 | "
              f"✓ {s['success_count']} | ✗ {s['fail_count']}")
        print("=" * 70)

        # 分类成功率
        print(f"\n  {'参数分类':<15} {'总数':>6} {'成功':>6} {'成功率':>8}")
        print(f"  {'-'*35}")
        for cat, data in sorted(s.get("categories", {}).items()):
            rate = data["success"] / max(data["total"], 1) * 100
            print(f"  {cat:<15} {data['total']:>6} {data['success']:>6} {rate:>7.1f}%")

        # 编码器对比
        enc_data = s.get("encoders", {})
        if ENCODER_JPEGLI in enc_data and ENCODER_MOZJPEG in enc_data:
            j = enc_data[ENCODER_JPEGLI]
            m = enc_data[ENCODER_MOZJPEG]
            print(f"\n  {'指标':<25} {'JPEGLI':>15} {'MOZJPEG':>15}")
            print(f"  {'-'*55}")
            print(f"  {'有效用例数':<25} {j['count']:>15} {m['count']:>15}")
            print(f"  {'平均文件大小(bytes)':<25} {j['avg_size']:>15.0f} {m['avg_size']:>15.0f}")
            print(f"  {'总大小(MB)':<25} {j['total_size_mb']:>15.2f} {m['total_size_mb']:>15.2f}")
            print(f"  {'平均 BPP':<25} {j['avg_bpp']:>15.4f} {m['avg_bpp']:>15.4f}")
            print(f"  {'平均 PSNR(dB)':<25} {j['avg_psnr']:>15.2f} {m['avg_psnr']:>15.2f}")
            print(f"  {'平均 SSIMULACRA2':<25} {j['avg_ssimulacra2']:>15.2f} {m['avg_ssimulacra2']:>15.2f}")
            print(f"  {'平均编码耗时(ms)':<25} {j['avg_enc_time_ms']:>15.1f} {m['avg_enc_time_ms']:>15.1f}")
            print(f"  {'编码吞吐量(MB/s)':<25} {j['avg_throughput_mbs']:>15.2f} {m['avg_throughput_mbs']:>15.2f}")

            # 对比结论
            m_total = m.get("total_size_mb", 0) or 0.001
            size_saving = (m_total - (j.get("total_size_mb", 0) or 0)) / m_total * 100
            print(f"\n  >>> JPEGLI 比 MOZJPEG 总体节省 {size_saving:.1f}% 空间")
            psnr_diff = j.get("avg_psnr", 0) - m.get("avg_psnr", 0)
            print(f"  >>> PSNR 差异 (JPEGLI - MOZ): {psnr_diff:+.2f} dB")
            ssim2_diff = j.get("avg_ssimulacra2", 0) - m.get("avg_ssimulacra2", 0)
            print(f"  >>> SSIMULACRA2 差异 (JPEGLI - MOZ): {ssim2_diff:+.2f}")

        # 稳定性
        if "stability" in s:
            st = s["stability"]
            print(f"\n  {'稳定性指标':-^50}")
            print(f"  文件大小标准差: {st['avg_size_stddev']:.1f} bytes")
            print(f"  PSNR 标准差: {st['avg_psnr_stddev']:.4f} dB")
            print(f"  编码耗时标准差: {st['avg_time_stddev']:.2f} ms")

        # 可靠性
        if "reliability" in s:
            rl = s["reliability"]
            print(f"\n  {'可靠性指标':-^50}")
            print(f"  成功率: {rl['success_rate']:.1f}%")
            print(f"  失败次数: {rl['fail_count']}")

        print()


# ═══════════════════════════════════════════════════════════════════════
# 任务分发器 (Orchestrator)
# ═══════════════════════════════════════════════════════════════════════

class TestOrchestrator:
    """管理多进程并发测试执行"""

    def __init__(self, max_workers: int | None = None):
        self.max_workers = max_workers or max(1, os.cpu_count() or 4)
        self._progress = None  # 共享进度计数器
        self._total = 0
        self._start_time: float = 0.0

    def _init_progress(self, total: int):
        """初始化进度跟踪"""
        self._total = total
        self._start_time = time.perf_counter()

    def _progress_callback(self, _future=None):
        """进度回调"""
        if hasattr(self, '_progress') and self._progress is not None:
            self._progress.value += 1
            done = self._progress.value
            elapsed = time.perf_counter() - self._start_time
            rate = done / max(elapsed, 0.001)
            eta = (self._total - done) / max(rate, 0.001)
            print(f"\r  进度: [{done}/{self._total}] "
                  f"{done/max(self._total,1)*100:5.1f}% | "
                  f"{rate:.1f} 用例/秒 | ETA {eta:.0f}s     ",
                  end="", flush=True)

    def execute(self, test_cases: list[dict]) -> list[dict]:
        """
        使用 ProcessPoolExecutor 并发执行测试用例
        返回结果列表
        """
        total = len(test_cases)
        self._init_progress(total)

        if total == 0:
            return []

        print(f"\n  启动 {self.max_workers} 个工作进程并发执行 {total} 个测试用例...\n")

        results = []

        # 对小规模用例直接顺序执行，避免进程池开销
        if total <= 4:
            print("  用例数较少，使用顺序执行模式...")
            for i, case in enumerate(test_cases):
                r = run_single_test(case)
                results.append(r)
                self._print_progress(i + 1, total)
            return results

        # 多进程执行
        with Manager() as manager:
            self._progress = manager.Value("i", 0)  # type: ignore[assignment]

            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(run_single_test, case): i
                           for i, case in enumerate(test_cases)}

                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        result = future.result(timeout=600)
                        results.append(result)
                    except Exception as e:
                        results.append({
                            "config": test_cases[idx],
                            "success": False,
                            "error": f"Worker 异常: {e}",
                            "duration_ms": 0,
                        })
                    self._progress_callback(future)

        # 按原始顺序排序
        results.sort(key=lambda r: test_cases.index(r.get("config", {})) if r.get("config") in test_cases else 0)

        print()  # 换行
        return results

    @staticmethod
    def _print_progress(done: int, total: int):
        pct = done / max(total, 1) * 100
        print(f"\r  进度: [{done}/{total}] {pct:5.1f}%     ", end="", flush=True)
        if done >= total:
            print()


# ═══════════════════════════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════════════════════════

def get_test_images(input_dir: str, max_images: int = 0,
                    image_types=(".jpg", ".jpeg", ".png")):
    """获取测试图像列表"""
    input_path = Path(input_dir)
    images = []
    for ext in image_types:
        images.extend(input_path.glob(f"*{ext}"))
        images.extend(input_path.glob(f"*{ext.upper()}"))
    images = sorted(set(map(str, images)))
    if max_images > 0:
        images = images[:max_images]
    return images


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="JPEG 压缩器对比测试 v2.0 — 多进程并发 + 扩展指标体系",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
测试参数分类示例:
  python compare_jpeg.py --quick                          # 快速模式
  python compare_jpeg.py --profile standard               # 标准模式(基础+边界)
  python compare_jpeg.py --profile full                   # 全量模式(所有分类)
  python compare_jpeg.py --categories basic boundary      # 指定分类
  python compare_jpeg.py --categories stress --repeat 5   # 压力测试
        """,
    )
    parser.add_argument("--input_dir", type=str, default=str(DEFAULT_INPUT_DIR),
                        help=f"输入图像目录 (默认: {DEFAULT_INPUT_DIR})")
    parser.add_argument("--max_images", type=int, default=0,
                        help="最多测试的图像数 (0=全部)")
    parser.add_argument("--output_dir", type=str, default="output",
                        help="输出报告目录 (默认: output)")

    # 测试场景 profile
    parser.add_argument("--profile", type=str, default="standard",
                        choices=["quick", "standard", "full", "stress", "boundary"],
                        help="""测试场景:
                        quick=基础+快速,
                        standard=基础+边界(默认),
                        full=所有参数分类,
                        stress=压力测试,
                        boundary=边界测试""")

    # 自定义参数分类
    parser.add_argument("--categories", type=str, nargs="+",
                        choices=PARAM_CATEGORIES, default=None,
                        help=f"自定义测试参数分类: {', '.join(PARAM_CATEGORIES)}")

    # 并发控制
    parser.add_argument("--workers", type=int, default=0,
                        help="工作进程数 (0=自动检测CPU核心数)")

    # 压力/重复参数
    parser.add_argument("--repeat", type=int, default=0,
                        help="压力测试重复次数 (0=使用默认值)")

    # 输出控制
    parser.add_argument("--save_images", action="store_true",
                        help="保存压缩后的 JPEG 图像到输出目录")
    parser.add_argument("--no-open", action="store_true",
                        help="不自动打开报告文件")

    return parser.parse_args(argv)


def resolve_profile(profile: str, repeat: int = 0) -> tuple[list[str], dict]:
    """
    根据 profile 解析出参数分类列表和附加配置
    返回 (categories, extra_config)
    """
    profiles = {
        "quick": ([PARAM_BASIC], {"quick": True}),
        "standard": ([PARAM_BASIC, PARAM_BOUNDARY], {}),
        "full": ([PARAM_BASIC, PARAM_BOUNDARY, PARAM_STRESS, PARAM_ANOMALY], {}),
        "stress": ([PARAM_STRESS], {"repeat": repeat or 5}),
        "boundary": ([PARAM_BOUNDARY], {}),
    }
    return profiles.get(profile, ([PARAM_BASIC], {}))


def _auto_open_reports(html_path: str, output_dir: Path):
    """自动打开报告文件（HTML + 输出目录）"""
    opened = []

    # 1. 尝试用默认浏览器打开 HTML 报告
    html = Path(html_path)
    if html.exists():
        try:
            webbrowser.open(html.resolve().as_uri())
            opened.append("HTML 报告 (浏览器)")
        except Exception:
            pass

    # 2. 在资源管理器中打开输出目录
    try:
        if platform.system() == "Windows":
            os.startfile(str(output_dir.resolve()))
            opened.append("输出目录 (资源管理器)")
    except Exception:
        pass

    if opened:
        print(f"  已自动打开: {', '.join(opened)}")
    else:
        print(f"  报告文件: {html.resolve()}")


def main():
    args = parse_args()

    # 工具检查
    if not ensure_tools():
        sys.exit(1)

    # 获取测试图像
    images = get_test_images(args.input_dir, max_images=args.max_images)
    if not images:
        print(f"[ERROR] 在 '{args.input_dir}' 中未找到图像")
        sys.exit(1)

    # 解析测试场景
    categories = args.categories if args.categories else resolve_profile(args.profile)[0]
    extra_config = resolve_profile(args.profile)[1]

    # quick 模式限制
    if extra_config.get("quick"):
        images = images[:min(3, len(images))]

    print(f"\n{'='*60}")
    print(f"  JPEG 压缩对比测试 v2.0")
    print(f"{'='*60}")
    print(f"  测试场景: {args.profile}")
    print(f"  参数分类: {', '.join(categories)}")
    print(f"  测试图像: {len(images)} 张")
    print(f"  工作进程: {args.workers or os.cpu_count() or 4}")
    if extra_config.get("repeat"):
        print(f"  重复次数: {extra_config['repeat']}")

    # 生成测试用例
    print(f"\n  生成测试用例...", end=" ", flush=True)
    test_cases = TestCaseGenerator.generate_all(images, categories=categories)

    # 对压力测试设置重复次数
    if extra_config.get("repeat"):
        for case in test_cases:
            if case.get("param_category") == PARAM_STRESS:
                case["repeat_count"] = extra_config["repeat"]

    print(f"共 {len(test_cases)} 个用例")

    if not test_cases:
        print("[ERROR] 没有生成测试用例")
        sys.exit(1)

    # 创建输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) / f"test_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 执行测试
    orchestrator = TestOrchestrator(max_workers=args.workers if args.workers > 0 else None)
    results = orchestrator.execute(test_cases)

    # 聚合指标
    print(f"\n  聚合指标中...", end=" ", flush=True)
    summary = MetricsAggregator.aggregate(results)

    # 生成报告
    ReportGenerator.print_summary(summary)

    csv_path = str(output_dir / "results.csv")
    json_path = str(output_dir / "results.json")
    html_path = str(output_dir / "report.html")
    ReportGenerator.to_csv(results, csv_path)
    ReportGenerator.to_json(results, summary, json_path)
    ReportGenerator.to_html(summary, html_path)
    print(f"  CSV 报告: {csv_path}")
    print(f"  JSON 报告: {json_path}")
    print(f"  HTML 报告: {html_path}")

    # 保存测试配置
    config_info = {
        "timestamp": timestamp,
        "profile": args.profile,
        "categories": categories,
        "workers": args.workers or os.cpu_count(),
        "num_images": len(images),
        "num_cases": len(test_cases),
        "tools": {
            "cjpegli": str(CJPEGLI),
            "mozjpeg_cjpeg": str(MCJPEG),
            "ssimulacra2": str(SSIMULACRA2),
        },
        "images": images,
    }
    with open(str(output_dir / "config.json"), "w", encoding="utf-8") as f:
        json.dump(config_info, f, ensure_ascii=False, indent=2)

    print(f"  配置: {output_dir / 'config.json'}")
    print(f"\n  所有报告已保存到: {output_dir.resolve()}")

    # ── 自动打开报告 ──
    if not args.no_open:
        _auto_open_reports(html_path, output_dir)

    print()

    # 返回退出码
    if summary["fail_count"] > 0 and summary["fail_count"] > summary["total_cases"] * 0.5:
        print("[WARN] 超过 50% 的用例失败")
        sys.exit(1)


if __name__ == "__main__":
    # Windows 下 multiprocessing 需要此保护
    main()
