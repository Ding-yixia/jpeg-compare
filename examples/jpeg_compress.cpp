/**
 * jpeg_compress.cpp — 多进程 JPEG 压缩程序
 *
 * 使用 libjpeg API 压缩图像，支持两种编码器后端:
 *   - jpegli: 链接 jpegli-static.lib
 *   - mozjpeg: 链接 jpeg.lib
 *
 * 编译:
 *   JPEGLI 版:
 *     cl.exe jpeg_compress.cpp -I lib/jpegli/include/jpegli lib/jpegli/jpegli-static.lib
 *                              lib/jpegli/zlib.lib /link /out:jpegli_compress.exe
 *
 *   MOZJPEG 版:
 *     cl.exe jpeg_compress.cpp -I lib/mozjpeg/include lib/mozjpeg/jpeg.lib
 *                              /link /out:mozjpeg_compress.exe
 *
 * 用法:
 *   jpegli_compress.exe input.ppm output.jpg 90
 *   mozjpeg_compress.exe input.ppm output.jpg 85
 */

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <chrono>
#include <csetjmp>

/* libjpeg API — 所有兼容库都提供 jpeglib.h */
#include "jpeglib.h"

/* ================================================================
 * PPM 读写
 * ================================================================ */

struct Image {
    unsigned char* data = nullptr;
    int width = 0;
    int height = 0;
    int channels = 3;

    ~Image() { delete[] data; }
    bool valid() const { return data != nullptr; }
};

Image read_ppm(const char* path) {
    Image img;
    FILE* fp = fopen(path, "rb");
    if (!fp) { fprintf(stderr, "无法打开: %s\n", path); return img; }

    char magic[3];
    int max_val;
    if (fscanf(fp, "%2s\n%d %d\n%d\n", magic, &img.width, &img.height, &max_val) < 4) {
        fprintf(stderr, "PPM 头解析失败\n");
        fclose(fp);
        return img;
    }

    if (magic[0] != 'P' || magic[1] != '6') {
        fprintf(stderr, "仅支持 P6 PPM, 收到: %s\n", magic);
        fclose(fp);
        return img;
    }

    img.channels = 3;
    img.data = new unsigned char[img.width * img.height * 3];
    size_t read = fread(img.data, 1, img.width * img.height * 3, fp);
    if (read != (size_t)img.width * img.height * 3) {
        fprintf(stderr, "PPM 数据不完整: 期望 %d, 读取 %zu\n",
                img.width * img.height * 3, (int)read);
        delete[] img.data;
        img.data = nullptr;
    }
    fclose(fp);
    return img;
}

/* ================================================================
 * JPEG 压缩 — 使用 libjpeg API
 * ================================================================ */

struct jpeg_error_mgr_wrap {
    struct jpeg_error_mgr pub;
    jmp_buf setjmp_buffer;
};

static void jpeg_error_handler(j_common_ptr cinfo) {
    jpeg_error_mgr_wrap* myerr = (jpeg_error_mgr_wrap*)cinfo->err;
    (*cinfo->err->output_message)(cinfo);
    longjmp(myerr->setjmp_buffer, 1);
}

bool compress_jpeg(const Image& img, const char* output_path,
                   int quality, bool jpegli_mode) {
    FILE* fp = fopen(output_path, "wb");
    if (!fp) { fprintf(stderr, "无法创建: %s\n", output_path); return false; }

    struct jpeg_compress_struct cinfo;
    struct jpeg_error_mgr_wrap jerr;
    cinfo.err = jpeg_std_error(&jerr.pub);
    jerr.pub.error_exit = jpeg_error_handler;

    if (setjmp(jerr.setjmp_buffer)) {
        jpeg_destroy_compress(&cinfo);
        fclose(fp);
        return false;
    }

    jpeg_create_compress(&cinfo);
    jpeg_stdio_dest(&cinfo, fp);

    cinfo.image_width = img.width;
    cinfo.image_height = img.height;
    cinfo.input_components = 3;
    cinfo.in_color_space = JCS_RGB;

    jpeg_set_defaults(&cinfo);
    jpeg_set_quality(&cinfo, quality, TRUE);

    /* jpegli 支持 4:4:4 高质量采样 */
    if (jpegli_mode) {
        cinfo.comp_info[0].h_samp_factor = 1;
        cinfo.comp_info[0].v_samp_factor = 1;
    }

    jpeg_start_compress(&cinfo, TRUE);

    int row_stride = img.width * 3;
    JSAMPROW row_pointer[1];
    while (cinfo.next_scanline < cinfo.image_height) {
        row_pointer[0] = (JSAMPROW)&img.data[cinfo.next_scanline * row_stride];
        jpeg_write_scanlines(&cinfo, row_pointer, 1);
    }

    jpeg_finish_compress(&cinfo);
    jpeg_destroy_compress(&cinfo);
    fclose(fp);
    return true;
}

/* ================================================================
 * 主程序
 * ================================================================ */

void print_usage(const char* prog) {
    fprintf(stderr, "用法: %s <input.ppm> <output.jpg> <quality 1-100> [--jpegli|--mozjpeg]\n", prog);
    fprintf(stderr, "示例: %s input.ppm output.jpg 90 --jpegli\n", prog);
}

int main(int argc, char* argv[]) {
    if (argc < 4) {
        print_usage(argv[0]);
        return 1;
    }

    const char* input_path  = argv[1];
    const char* output_path = argv[2];
    int quality = atoi(argv[3]);
    bool jpegli_mode = true;

    if (argc >= 5) {
        jpegli_mode = (strcmp(argv[4], "--jpegli") == 0);
    }

    if (quality < 1 || quality > 100) {
        fprintf(stderr, "质量值必须在 1-100 之间\n");
        return 1;
    }

    /* 读取 PPM */
    auto t0 = std::chrono::high_resolution_clock::now();
    Image img = read_ppm(input_path);
    if (!img.valid()) return 1;
    auto t1 = std::chrono::high_resolution_clock::now();

    /* 编码 JPEG */
    bool ok = compress_jpeg(img, output_path, quality, jpegli_mode);
    if (!ok) {
        fprintf(stderr, "JPEG 编码失败\n");
        return 1;
    }
    auto t2 = std::chrono::high_resolution_clock::now();

    /* 统计 */
    FILE* fp = fopen(output_path, "rb");
    long file_size = 0;
    if (fp) { fseek(fp, 0, SEEK_END); file_size = ftell(fp); fclose(fp); }

    double read_ms  = std::chrono::duration<double, std::milli>(t1 - t0).count();
    double enc_ms   = std::chrono::duration<double, std::milli>(t2 - t1).count();
    double bpp      = (double)file_size * 8.0 / (img.width * img.height);

    const char* backend = jpegli_mode ? "JPEGLI" : "MOZJPEG";

    printf("\n");
    printf("╔══════════════════════════════════════╗\n");
    printf("║  JPEG 压缩报告                        ║\n");
    printf("╠══════════════════════════════════════╣\n");
    printf("║  编码后端 : %-26s ║\n", backend);
    printf("║  输入文件 : %-26s ║\n", input_path);
    printf("║  输出文件 : %-26s ║\n", output_path);
    printf("║  分辨率   : %-4d x %-20d ║\n", img.width, img.height);
    printf("║  质量     : %-26d ║\n", quality);
    printf("║────────────┬─────────────────────────╢\n");
    printf("║  文件大小  : %-26s ║\n", file_size > 1024*1024 ?
           ({
               static char buf[32];
               snprintf(buf, 32, "%.2f MB", file_size/(1024.*1024));
               buf;
           }) : ({
               static char buf[32];
               snprintf(buf, 32, "%.1f KB", file_size/1024.);
               buf;
           }));
    printf("║  BPP      : %-26.4f ║\n", bpp);
    printf("║  读取耗时 : %-26.1f ║\n", read_ms);
    printf("║  编码耗时 : %-26.1f ║\n", enc_ms);
    printf("║  吞吐量   : %-26.2f ║\n", file_size / 1024. / 1024. / (enc_ms / 1000.));
    printf("╚══════════════════════════════════════╝\n");

    return 0;
}
