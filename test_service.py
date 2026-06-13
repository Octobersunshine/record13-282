import os
import sys
import json
import base64
import struct
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base64_image_service import Base64ImageService


def create_test_png(filepath, width=10, height=10, color=(255, 100, 50)):
    def chunk(chunk_type, data):
        chunk_data = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(chunk_data) & 0xffffffff)
        return struct.pack('>I', len(data)) + chunk_data + crc

    signature = b'\x89PNG\r\n\x1a\n'

    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = chunk(b'IHDR', ihdr_data)

    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'
        for x in range(width):
            raw_data += bytes(color)

    compressed = zlib.compress(raw_data)
    idat = chunk(b'IDAT', compressed)

    iend = chunk(b'IEND', b'')

    png_data = signature + ihdr + idat + iend

    os.makedirs(os.path.dirname(os.path.abspath(filepath)) or '.', exist_ok=True)
    with open(filepath, 'wb') as f:
        f.write(png_data)

    return filepath


def run_tests():
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_output')
    os.makedirs(test_dir, exist_ok=True)

    print("=" * 60)
    print("Base64 图片嵌入服务 - 测试套件")
    print("=" * 60)

    test_image1 = os.path.join(test_dir, 'test_image1.png')
    test_image2 = os.path.join(test_dir, 'test_image2.png')
    create_test_png(test_image1, 20, 20, (255, 100, 50))
    create_test_png(test_image2, 30, 15, (50, 150, 255))
    print(f"\n[✓] 已创建测试图片:")
    print(f"    - {test_image1}")
    print(f"    - {test_image2}")

    print("\n" + "-" * 60)
    print("测试 1: 图片文件编码为 DataURL")
    print("-" * 60)
    data_url1 = Base64ImageService.encode_file(test_image1)
    assert data_url1.startswith('data:image/png;base64,'), "DataURL 格式错误"
    print(f"[✓] 编码成功，长度: {len(data_url1)} 字符")
    print(f"    前缀: {data_url1[:50]}...")

    print("\n" + "-" * 60)
    print("测试 2: 字节数据编码为 DataURL")
    print("-" * 60)
    with open(test_image1, 'rb') as f:
        img_bytes = f.read()
    data_url2 = Base64ImageService.encode_bytes(img_bytes, 'image/png')
    assert data_url1 == data_url2, "字节编码与文件编码结果不一致"
    print("[✓] 字节编码成功，结果与文件编码一致")

    print("\n" + "-" * 60)
    print("测试 3: DataURL 解码为字节")
    print("-" * 60)
    decoded_bytes, mime_type = Base64ImageService.decode_to_bytes(data_url1)
    assert len(decoded_bytes) == len(img_bytes), "解码后字节数不匹配"
    assert decoded_bytes == img_bytes, "解码后数据不匹配"
    assert mime_type == 'image/png', "MIME 类型错误"
    print(f"[✓] 解码成功，大小: {len(decoded_bytes)} 字节，MIME: {mime_type}")

    print("\n" + "-" * 60)
    print("测试 4: DataURL 还原为图片文件")
    print("-" * 60)
    restored_path = os.path.join(test_dir, 'restored_image.png')
    result_path = Base64ImageService.decode_to_file(data_url1, restored_path)
    assert os.path.isfile(result_path), "还原文件不存在"
    with open(result_path, 'rb') as f:
        restored_bytes = f.read()
    assert restored_bytes == img_bytes, "还原后文件内容不匹配"
    print(f"[✓] 文件还原成功: {result_path}")

    print("\n" + "-" * 60)
    print("测试 5: 嵌入 HTML 单张图片")
    print("-" * 60)
    img_tag = Base64ImageService.embed_in_html(test_image1, alt_text='测试图片', width='200px')
    assert '<img' in img_tag and 'src="data:image/png;base64,' in img_tag, "HTML 嵌入格式错误"
    assert 'alt="测试图片"' in img_tag, "alt 属性缺失"
    assert 'width="200px"' in img_tag, "width 属性缺失"
    print(f"[✓] HTML 嵌入成功，标签长度: {len(img_tag)} 字符")

    print("\n" + "-" * 60)
    print("测试 6: 生成完整 HTML 页面")
    print("-" * 60)
    images = [
        {'path': test_image1, 'alt': '图片1', 'width': '100px'},
        {'path': test_image2, 'alt': '图片2', 'width': '150px'},
    ]
    html_path = os.path.join(test_dir, 'gallery.html')
    html_content = Base64ImageService.create_html_page(images, title='测试图库', output_path=html_path)
    assert os.path.isfile(html_path), "HTML 文件未生成"
    assert '<!DOCTYPE html>' in html_content, "HTML 格式错误"
    assert '测试图库' in html_content, "标题缺失"
    print(f"[✓] HTML 页面生成成功: {html_path}")

    print("\n" + "-" * 60)
    print("测试 7: 嵌入 JSON 单张图片")
    print("-" * 60)
    json_obj = Base64ImageService.embed_in_json(test_image1, key='avatar')
    assert 'avatar' in json_obj, "JSON key 缺失"
    assert json_obj['avatar'].startswith('data:image/png;base64,'), "JSON 值格式错误"
    print(f"[✓] JSON 嵌入成功，key: avatar")

    print("\n" + "-" * 60)
    print("测试 8: 生成完整 JSON 负载")
    print("-" * 60)
    json_images = [
        {'path': test_image1, 'key': 'thumbnail'},
        {'path': test_image2, 'key': 'banner'},
    ]
    json_path = os.path.join(test_dir, 'images.json')
    json_payload = Base64ImageService.create_json_payload(json_images, output_path=json_path)
    assert os.path.isfile(json_path), "JSON 文件未生成"
    assert 'thumbnail' in json_payload and 'banner' in json_payload, "JSON keys 缺失"
    print(f"[✓] JSON 负载生成成功: {json_path}")
    print(f"    包含 {len(json_payload)} 张图片数据")

    print("\n" + "-" * 60)
    print("测试 9: 从 HTML 中提取图片")
    print("-" * 60)
    extracted_from_html = Base64ImageService.extract_from_html(html_content)
    assert len(extracted_from_html) == 2, f"应提取 2 张图片，实际提取 {len(extracted_from_html)} 张"
    print(f"[✓] 从 HTML 中提取到 {len(extracted_from_html)} 张图片")
    for i, item in enumerate(extracted_from_html):
        print(f"    图片 {i+1}: MIME={item['mime_type']}, 大小={item['size_bytes']} 字节")

    print("\n" + "-" * 60)
    print("测试 10: 从 JSON 中提取图片")
    print("-" * 60)
    with open(json_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    extracted_from_json = Base64ImageService.extract_from_json(json_data)
    assert len(extracted_from_json) == 2, f"应提取 2 张图片，实际提取 {len(extracted_from_json)} 张"
    print(f"[✓] 从 JSON 中提取到 {len(extracted_from_json)} 张图片")
    for i, item in enumerate(extracted_from_json):
        print(f"    图片 {i+1}: 路径={item['path']}, MIME={item['mime_type']}")

    print("\n" + "-" * 60)
    print("测试 11: 提取并保存为文件")
    print("-" * 60)
    extract_dir = os.path.join(test_dir, 'extracted')
    saved_files = Base64ImageService.extract_and_save(
        html_content, source_type='html', output_dir=extract_dir
    )
    assert len(saved_files) == 2, "保存文件数量不匹配"
    for f in saved_files:
        assert os.path.isfile(f), f"文件不存在: {f}"
    print(f"[✓] 成功提取并保存 {len(saved_files)} 个文件:")
    for f in saved_files:
        print(f"    - {f}")

    print("\n" + "-" * 60)
    print("测试 12: 支持的图片格式检测")
    print("-" * 60)
    supported = Base64ImageService.MIME_TYPE_MAP
    print(f"[✓] 支持 {len(supported)} 种图片格式:")
    for ext, mime in supported.items():
        print(f"    {ext} -> {mime}")

    print("\n" + "=" * 60)
    print("所有测试通过! ✓")
    print("=" * 60)
    print(f"\n测试输出目录: {test_dir}")
    print("\n生成的文件:")
    for root, dirs, files in os.walk(test_dir):
        for f in files:
            filepath = os.path.join(root, f)
            size = os.path.getsize(filepath)
            print(f"  {os.path.relpath(filepath, test_dir)} ({size} 字节)")


if __name__ == '__main__':
    run_tests()
