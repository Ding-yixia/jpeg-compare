#include <cstdio>
#include \"jpeglib.h\"
int main() {
    printf(\"sizeof(jpeg_compress_struct) = %zu\\n\", sizeof(jpeg_compress_struct));
    struct jpeg_compress_struct cinfo;
    struct jpeg_error_mgr jerr;
    cinfo.err = jpeg_std_error(&jerr);
    printf(\"jpeg_std_error OK\\n\");
    jpeg_create_compress(&cinfo);
    printf(\"jpeg_create_compress OK\\n\");
    jpeg_destroy_compress(&cinfo);
    printf(\"jpeg_destroy_compress OK\\n\");
    return 0;
}
