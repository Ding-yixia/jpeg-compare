cmake_minimum_required(VERSION 3.16)
project(jpeg-compare-examples LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── JPEGLI 示例 ──
add_executable(jpegli_compress examples/jpeg_compress.cpp)
target_include_directories(jpegli_compress PRIVATE lib/jpegli/include/jpegli)
target_link_libraries(jpegli_compress PRIVATE
    "${CMAKE_SOURCE_DIR}/lib/jpegli/jpegli-static.lib"
    "${CMAKE_SOURCE_DIR}/lib/jpegli/zlib.lib")

# ── MOZJPEG 示例 ──
add_executable(mozjpeg_compress examples/jpeg_compress.cpp)
target_compile_definitions(mozjpeg_compress PRIVATE MOZJPEG)
target_include_directories(mozjpeg_compress PRIVATE lib/mozjpeg/include)
target_link_libraries(mozjpeg_compress PRIVATE
    "${CMAKE_SOURCE_DIR}/lib/mozjpeg/jpeg.lib")

# ── 质量指标程序 ──
add_executable(jpeg_quality examples/jpeg_quality.cpp)
target_include_directories(jpeg_quality PRIVATE lib/jpegli/include/jpegli)
