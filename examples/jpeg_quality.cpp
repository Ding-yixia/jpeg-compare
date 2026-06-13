/**
 * jpeg_quality.cpp — 图像质量指标评测程序
 *
 * 计算两幅图像之间的质量指标:
 *   - PSNR (Peak Signal-to-Noise Ratio)
 *   - SSIM (Structural Similarity Index)
 *
 * 编译:
 *   cl.exe jpeg_quality.cpp /EHsc /O2 /std:c++17
 *
 * 用法:
 *   jpeg_quality.exe original.ppm decoded.ppm
 *   jpeg_quality.exe original.png decoded.png
 */

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <vector>
#include <algorithm>
#include <chrono>

/* ================================================================
 * 简单的 PPM/PNM 读写 (仅 P6/P5)
 * ================================================================ */

struct Image {
    std::vector<unsigned char> data;
    int width = 0;
    int height = 0;
    int channels = 3;

    bool load_ppm(const char* path) {
        FILE* fp = fopen(path, "rb");
        if (!fp) { fprintf(stderr, "[ERROR] 无法打开: %s\n", path); return false; }

        char magic[3];
        int max_val;
        if (fscanf(fp, "%2s\n%d %d\n%d\n", magic, &width, &height, &max_val) < 4) {
            fprintf(stderr, "[ERROR] 头解析失败: %s\n", path);
            fclose(fp);
            return false;
        }

        if (magic[0] != 'P' || (magic[1] != '6' && magic[1] != '5')) {
            fprintf(stderr, "[ERROR] 仅支持 P6/P5 PNM, 收到: %s\n", magic);
            fclose(fp);
            return false;
        }

        channels = (magic[1] == '6') ? 3 : 1;
        data.resize(width * height * channels);
        size_t read = fread(data.data(), 1, data.size(), fp);
        fclose(fp);

        if (read != data.size()) {
            fprintf(stderr, "[WARN] 数据不完整: 期望 %zu, 读取 %zu (尝试继续)\n", data.size(), read);
            data.resize(read);
        }
        return true;
    }

    bool valid() const { return !data.empty(); }
};

/* ================================================================
 * 积分图像 (Summed-Area Table) — 快速均匀滤波
 * ================================================================ */

void integral_image(const float* src, int h, int w, float* sat) {
    /* SAT[i,j] = sum of src[0..i, 0..j] */
    for (int i = 0; i < h; i++) {
        float row_sum = 0;
        for (int j = 0; j < w; j++) {
            row_sum += src[i * w + j];
            float above = (i > 0) ? sat[(i - 1) * w + j] : 0;
            sat[i * w + j] = above + row_sum;
        }
    }
}

float box_filter(const float* sat, int h, int w, int i, int j, int size) {
    int pad = size / 2;
    int y1 = std::max(0, i - pad);
    int y2 = std::min(h - 1, i + pad);
    int x1 = std::max(0, j - pad);
    int x2 = std::min(w - 1, j + pad);
    int area = (y2 - y1 + 1) * (x2 - x1 + 1);

    float sum = sat[y2 * w + x2];
    if (y1 > 0) sum -= sat[(y1 - 1) * w + x2];
    if (x1 > 0) sum -= sat[y2 * w + (x1 - 1)];
    if (y1 > 0 && x1 > 0) sum += sat[(y1 - 1) * w + (x1 - 1)];
    return sum / area;
}

/* ================================================================
 * PSNR
 * ================================================================ */

double compute_psnr(const Image& img1, const Image& img2) {
    if (img1.width != img2.width || img1.height != img2.height ||
        img1.channels != img2.channels) {
        fprintf(stderr, "[ERROR] 图像尺寸不匹配\n");
        return -1;
    }

    double mse = 0;
    size_t n = img1.data.size();
    for (size_t i = 0; i < n; i++) {
        double diff = (double)img1.data[i] - (double)img2.data[i];
        mse += diff * diff;
    }
    mse /= n;

    if (mse == 0) return 100.0;  /* 无损 */
    return 20.0 * log10(255.0 / sqrt(mse));
}

/* ================================================================
 * SSIM
 * ================================================================ */

double compute_ssim(const Image& img1, const Image& img2) {
    if (img1.width != img2.width || img1.height != img2.height) {
        fprintf(stderr, "[ERROR] 图像尺寸不匹配\n");
        return -1;
    }

    int h = img1.height, w = img1.width, c = std::min(img1.channels, img2.channels);
    int n = h * w;
    int size = 11;  /* 11x11 窗口 */

    /* 转换为 float */
    std::vector<float> f1(n * c), f2(n * c);
    for (int i = 0; i < n * c; i++) {
        f1[i] = (float)img1.data[i];
        f2[i] = (float)img2.data[i];
    }

    const float C1 = (0.01f * 255.0f) * (0.01f * 255.0f);
    const float C2 = (0.03f * 255.0f) * (0.03f * 255.0f);

    double ssim_total = 0;

    for (int ch = 0; ch < c; ch++) {
        float* a = &f1[ch * n];
        float* b = &f2[ch * n];

        /* 积分图像 */
        std::vector<float> sat_a(n), sat_b(n), sat_a2(n), sat_b2(n), sat_ab(n);
        integral_image(a, h, w, sat_a.data());
        integral_image(b, h, w, sat_b.data());

        /* a^2, b^2, a*b */
        std::vector<float> a2(n), b2(n), ab(n);
        for (int i = 0; i < n; i++) {
            a2[i] = a[i] * a[i];
            b2[i] = b[i] * b[i];
            ab[i] = a[i] * b[i];
        }
        integral_image(a2.data(), h, w, sat_a2.data());
        integral_image(b2.data(), h, w, sat_b2.data());
        integral_image(ab.data(), h, w, sat_ab.data());

        double ssim_ch = 0;
        int pixels = 0;

        for (int i = 0; i < h; i++) {
            for (int j = 0; j < w; j++) {
                float mu1 = box_filter(sat_a.data(), h, w, i, j, size);
                float mu2 = box_filter(sat_b.data(), h, w, i, j, size);
                float sigma1_sq = box_filter(sat_a2.data(), h, w, i, j, size) - mu1 * mu1;
                float sigma2_sq = box_filter(sat_b2.data(), h, w, i, j, size) - mu2 * mu2;
                float sigma12   = box_filter(sat_ab.data(), h, w, i, j, size) - mu1 * mu2;

                float numerator   = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2);
                float denominator = (mu1 * mu1 + mu2 * mu2 + C1) * (sigma1_sq + sigma2_sq + C2);
                ssim_ch += numerator / denominator;
                pixels++;
            }
        }
        ssim_total += ssim_ch / pixels;
    }

    return ssim_total / c;
}

/* ================================================================
 * 主程序
 * ================================================================ */

int main(int argc, char* argv[]) {
    if (argc < 3) {
        fprintf(stderr, "用法: %s <original> <distorted>\n", argv[0]);
        fprintf(stderr, "示例: %s original.ppm decoded.ppm\n", argv[0]);
        fprintf(stderr, "支持格式: PPM (P6)\n");
        return 1;
    }

    printf("\n");
    printf("╔══════════════════════════════════════╗\n");
    printf("║  图像质量指标评测                      ║\n");
    printf("╠══════════════════════════════════════╣\n");

    Image img1, img2;
    if (!img1.load_ppm(argv[1])) return 1;
    if (!img2.load_ppm(argv[2])) return 1;

    printf("║  原始   : %-26s ║\n", argv[1]);
    printf("║  对比   : %-26s ║\n", argv[2]);
    printf("║  分辨率 : %-4d x %-20d ║\n", img1.width, img1.height);
    printf("║  通道数 : %-26d ║\n", img1.channels);
    printf("║────────────┬─────────────────────────╢\n");

    /* PSNR */
    auto t0 = std::chrono::high_resolution_clock::now();
    double psnr = compute_psnr(img1, img2);
    auto t1 = std::chrono::high_resolution_clock::now();
    double psnr_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

    if (psnr >= 0) {
        printf("║  PSNR     : %-26.2f ║\n", psnr);
        printf("║  PSNR耗时 : %-26.1f ║\n", psnr_ms);
    }

    /* SSIM */
    t0 = std::chrono::high_resolution_clock::now();
    double ssim = compute_ssim(img1, img2);
    t1 = std::chrono::high_resolution_clock::now();
    double ssim_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

    if (ssim >= 0) {
        printf("║  SSIM     : %-26.6f ║\n", ssim);
        printf("║  SSIM耗时 : %-26.1f ║\n", ssim_ms);
    }

    printf("╚══════════════════════════════════════╝\n");

    return 0;
}
