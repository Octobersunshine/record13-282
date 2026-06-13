import os
import sys
import json
import base64
import struct
import zlib
import warnings

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


def create_large_test_png(filepath, size_kb=50):
    width = 200
    height = (size_kb * 1024) // (width * 3) + 10
    return create_test_png(filepath, width=width, height=height, color=(100, 150, 200))


def run_tests():
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_output')
    os.makedirs(test_dir, exist_ok=True)

    print("=" * 60)
    print("Base64 图片嵌入服务 - 测试套件")
    print("=" * 60)

    test_image1 = os.path.join(test_dir, 'test_image1.png')
    test_image2 = os.path.join(test_dir, 'test_image2.png')
    large_image = os.path.join(test_dir, 'large_image.png')

    create_test_png(test_image1, 20, 20, (255, 100, 50))
    create_test_png(test_image2, 30, 15, (50, 150, 255))
    create_large_test_png(large_image, size_kb=50)

    print(f"\n[✓] 已创建测试图片:")
    print(f"    - {test_image1} ({os.path.getsize(test_image1)} 字节)")
    print(f"    - {test_image2} ({os.path.getsize(test_image2)} 字节)")
    print(f"    - {large_image} ({os.path.getsize(large_image)} 字节)")

    Base64ImageService.set_warnings_enabled(False)

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
    print("大图片处理专项测试")
    print("=" * 60)

    print("\n" + "-" * 60)
    print("测试 13: 图片文件信息检测")
    print("-" * 60)
    info = Base64ImageService.get_file_info(test_image1)
    assert info['size_bytes'] > 0, "文件大小应为正数"
    assert info['mime_type'] == 'image/png', "MIME 类型错误"
    assert 'size_human' in info, "缺少人类可读大小"
    assert 'base64_estimated_bytes' in info, "缺少预估大小"
    print(f"[✓] 文件信息检测成功:")
    print(f"    文件名: {info['filename']}")
    print(f"    大小: {info['size_human']}")
    print(f"    Base64 预估大小: {info['base64_estimated_human']}")
    print(f"    是否为大图片: {info['is_large']}")

    print("\n" + "-" * 60)
    print("测试 14: 大图片警告提示")
    print("-" * 60)
    original_warn_size = Base64ImageService.warn_size
    Base64ImageService.set_warn_size(50)
    Base64ImageService.set_warnings_enabled(True)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Base64ImageService.encode_file(test_image1)
        assert len(w) >= 1, "应该触发警告"
        assert issubclass(w[0].category, UserWarning), "应该是 UserWarning"
        print(f"[✓] 大图片警告正常触发: {w[0].message}")

    Base64ImageService.set_warn_size(original_warn_size)
    Base64ImageService.set_warnings_enabled(False)

    print("\n" + "-" * 60)
    print("测试 15: 压缩编码与解码（zlib）")
    print("-" * 60)
    compressed_data_url = Base64ImageService.encode_file(test_image1, compress=True)
    assert ';base64;zlib,' in compressed_data_url, "压缩 DataURL 格式错误"
    print(f"[✓] 压缩编码成功")
    print(f"    原始长度: {len(data_url1)} 字符")
    print(f"    压缩后长度: {len(compressed_data_url)} 字符")

    decoded_compressed, mime_compressed = Base64ImageService.decode_to_bytes(compressed_data_url)
    assert decoded_compressed == img_bytes, "压缩解码后数据不匹配"
    assert mime_compressed == 'image/png', "压缩后 MIME 类型错误"
    print(f"[✓] 压缩解码成功，数据完全一致")

    print("\n" + "-" * 60)
    print("测试 16: 字节数据压缩编码")
    print("-" * 60)
    compressed_bytes_url = Base64ImageService.encode_bytes(img_bytes, 'image/png', compress=True)
    assert ';base64;zlib,' in compressed_bytes_url, "压缩字节编码格式错误"
    decoded_cb, _ = Base64ImageService.decode_to_bytes(compressed_bytes_url)
    assert decoded_cb == img_bytes, "压缩字节解码后数据不匹配"
    print("[✓] 字节压缩编码与解码成功")

    print("\n" + "-" * 60)
    print("测试 17: 流式编码（大图片分块处理）")
    print("-" * 60)
    original_chunk = Base64ImageService.chunk_size
    Base64ImageService.set_chunk_size(100)

    stream_result = list(Base64ImageService.encode_file_streaming(test_image1))
    assert len(stream_result) > 1, "流式编码应该产生多个数据块"
    assert stream_result[0].startswith('data:image/png;base64,'), "首块应为 header"

    full_stream_url = ''.join(stream_result)
    assert full_stream_url == data_url1, "流式编码结果应与一次性编码一致"
    print(f"[✓] 流式编码成功")
    print(f"    分块数量: {len(stream_result)}")
    print(f"    拼接后与直接编码一致: 是")

    Base64ImageService.set_chunk_size(original_chunk)

    print("\n" + "-" * 60)
    print("测试 18: 流式编码 + 压缩")
    print("-" * 60)
    Base64ImageService.set_chunk_size(200)
    stream_compressed = list(Base64ImageService.encode_file_streaming(test_image1, compress=True))
    assert len(stream_compressed) > 1, "压缩流式编码应产生多个数据块"
    assert stream_compressed[0].startswith('data:image/png;base64;zlib,'), "压缩流式 header 格式错误"

    full_compressed_url = ''.join(stream_compressed)
    decoded_stream_comp, _ = Base64ImageService.decode_to_bytes(full_compressed_url)
    assert decoded_stream_comp == img_bytes, "压缩流式编码解码后数据不匹配"
    print(f"[✓] 压缩流式编码成功")
    print(f"    分块数量: {len(stream_compressed)}")
    print(f"    解码后数据一致: 是")

    Base64ImageService.set_chunk_size(original_chunk)

    print("\n" + "-" * 60)
    print("测试 19: 分段编码（JSON 分段存储）")
    print("-" * 60)
    original_seg_len = Base64ImageService.segment_length
    Base64ImageService.set_segment_length(30)

    segmented = Base64ImageService.encode_file_segmented(test_image1)
    assert segmented['total_segments'] > 1, "应该产生多个分段"
    assert len(segmented['segments']) == segmented['total_segments'], "分段数量不匹配"
    assert 'header' in segmented, "缺少 header"
    assert 'mime_type' in segmented, "缺少 mime_type"
    print(f"[✓] 分段编码成功")
    print(f"    分段数量: {segmented['total_segments']}")
    print(f"    每段长度: {segmented['segment_length']}")

    reassembled = Base64ImageService.reassemble_segmented(segmented)
    assert reassembled == data_url1, "分段重组后与原始 DataURL 不一致"
    print(f"[✓] 分段重组成功，与原始数据一致")

    Base64ImageService.set_segment_length(original_seg_len)

    print("\n" + "-" * 60)
    print("测试 20: 分段编码 + 压缩")
    print("-" * 60)
    Base64ImageService.set_segment_length(40)
    segmented_comp = Base64ImageService.encode_file_segmented(test_image1, compress=True)
    assert segmented_comp['compressed'] == True, "compressed 标记应为 True"
    assert 'zlib' in segmented_comp['header'], "header 应包含 zlib 标识"

    reassembled_comp = Base64ImageService.reassemble_segmented(segmented_comp)
    decoded_seg_comp, _ = Base64ImageService.decode_to_bytes(reassembled_comp)
    assert decoded_seg_comp == img_bytes, "分段压缩重组解码后数据不匹配"
    print(f"[✓] 分段压缩编码成功")
    print(f"    分段数量: {segmented_comp['total_segments']}")
    print(f"    解码后数据一致: 是")

    Base64ImageService.set_segment_length(original_seg_len)

    print("\n" + "-" * 60)
    print("测试 21: JSON 分段存储嵌入")
    print("-" * 60)
    Base64ImageService.set_segment_length(50)
    json_seg = Base64ImageService.embed_in_json(test_image1, key='photo', segmented=True)
    assert isinstance(json_seg['photo'], dict), "分段数据应为 dict"
    assert 'segments' in json_seg['photo'], "缺少 segments 字段"
    assert 'header' in json_seg['photo'], "缺少 header 字段"
    print(f"[✓] JSON 分段嵌入成功")
    print(f"    分段数: {len(json_seg['photo']['segments'])}")

    print("\n" + "-" * 60)
    print("测试 22: create_json_payload 分段模式")
    print("-" * 60)
    seg_json_images = [
        {'path': test_image1, 'key': 'img1', 'segmented': True},
        {'path': test_image2, 'key': 'img2', 'segmented': False},
    ]
    seg_json_path = os.path.join(test_dir, 'segmented_images.json')
    seg_payload = Base64ImageService.create_json_payload(
        seg_json_images, output_path=seg_json_path, segmented=False
    )
    assert seg_payload['img1']['segmented'] == True, "img1 应为分段模式"
    assert seg_payload['img2']['segmented'] == False, "img2 应为非分段模式"
    assert os.path.isfile(seg_json_path), "分段 JSON 文件未生成"
    print(f"[✓] 混合模式 JSON 负载生成成功")
    print(f"    分段图片: img1")
    print(f"    普通图片: img2")

    print("\n" + "-" * 60)
    print("测试 23: 从分段 JSON 中提取图片")
    print("-" * 60)
    with open(seg_json_path, 'r', encoding='utf-8') as f:
        seg_json_data = json.load(f)
    extracted_seg = Base64ImageService.extract_from_json(seg_json_data)
    assert len(extracted_seg) == 2, f"应提取 2 张图片，实际 {len(extracted_seg)} 张"

    seg_items = [x for x in extracted_seg if x.get('segmented')]
    normal_items = [x for x in extracted_seg if not x.get('segmented')]
    assert len(seg_items) == 1, "应有 1 张分段图片"
    assert len(normal_items) == 1, "应有 1 张普通图片"
    print(f"[✓] 从分段 JSON 中提取成功")
    print(f"    分段图片: {len(seg_items)} 张")
    print(f"    普通图片: {len(normal_items)} 张")

    for item in extracted_seg:
        decoded_item, _ = Base64ImageService.decode_to_bytes(item['data_url'])
        assert len(decoded_item) == item['size_bytes'], "提取的图片大小不匹配"
    print(f"[✓] 所有提取的图片数据验证通过")

    print("\n" + "-" * 60)
    print("测试 24: 压缩后大图片体积对比")
    print("-" * 60)
    large_original = Base64ImageService.encode_file(large_image, compress=False)
    large_compressed = Base64ImageService.encode_file(large_image, compress=True)

    orig_size = len(large_original)
    comp_size = len(large_compressed)
    ratio = (1 - comp_size / orig_size) * 100 if orig_size > 0 else 0

    print(f"[✓] 大图片压缩对比:")
    print(f"    原始大小: {Base64ImageService._format_size(orig_size)}")
    print(f"    压缩后大小: {Base64ImageService._format_size(comp_size)}")
    print(f"    压缩率: {ratio:.2f}%")

    decoded_large, _ = Base64ImageService.decode_to_bytes(large_compressed)
    with open(large_image, 'rb') as f:
        large_bytes = f.read()
    assert decoded_large == large_bytes, "大图片压缩解压后数据不匹配"
    print(f"[✓] 大图片压缩解压验证通过")

    print("\n" + "-" * 60)
    print("测试 25: 配置参数设置与读取")
    print("-" * 60)
    old_warn = Base64ImageService.warn_size
    old_chunk = Base64ImageService.chunk_size
    old_seg = Base64ImageService.segment_length

    Base64ImageService.set_warn_size(2 * 1024 * 1024)
    Base64ImageService.set_chunk_size(128 * 1024)
    Base64ImageService.set_segment_length(120)
    Base64ImageService.set_warnings_enabled(True)

    assert Base64ImageService.warn_size == 2 * 1024 * 1024
    assert Base64ImageService.chunk_size == 128 * 1024
    assert Base64ImageService.segment_length == 120
    assert Base64ImageService.enable_warnings == True

    Base64ImageService.set_warn_size(old_warn)
    Base64ImageService.set_chunk_size(old_chunk)
    Base64ImageService.set_segment_length(old_seg)
    Base64ImageService.set_warnings_enabled(False)

    print(f"[✓] 所有配置参数设置正常")

    print("\n" + "=" * 60)
    print("批量嵌入专项测试")
    print("=" * 60)

    print("\n" + "-" * 60)
    print("测试 26: 批量嵌入到目录（HTML + JSON + Manifest）")
    print("-" * 60)
    batch_images = [
        {'path': test_image1, 'key': 'logo', 'alt': 'Logo 图片', 'width': '100px'},
        {'path': test_image2, 'key': 'banner', 'alt': 'Banner 图片', 'width': '150px'},
        {'path': large_image, 'key': 'photo', 'alt': '大图照片', 'width': '300px'},
    ]
    batch_dir = os.path.join(test_dir, 'batch_output')
    batch_files = Base64ImageService.batch_embed_to_directory(
        batch_images, output_dir=batch_dir,
        include_html=True, include_json=True, include_manifest=True,
        compress=False, html_title='我的批量图库'
    )
    assert 'html' in batch_files, "缺少 HTML 文件"
    assert 'json' in batch_files, "缺少 JSON 文件"
    assert 'manifest' in batch_files, "缺少 Manifest 文件"
    for f in batch_files.values():
        assert os.path.isfile(f), f"文件不存在: {f}"
    print(f"[✓] 批量嵌入到目录成功")
    for k, v in batch_files.items():
        print(f"    {k}: {v} ({os.path.getsize(v)} 字节)")

    print("\n" + "-" * 60)
    print("测试 27: Manifest 清单内容验证")
    print("-" * 60)
    with open(batch_files['manifest'], 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    assert manifest['version'] == '1.0', "Manifest 版本错误"
    assert manifest['summary']['total_images'] == 3, "图片数量统计错误"
    assert 'settings' in manifest, "缺少 settings"
    assert 'images' in manifest, "缺少 images 列表"
    assert len(manifest['images']) == 3, "images 列表长度错误"
    for img_entry in manifest['images']:
        assert 'filename' in img_entry
        assert 'original_size_bytes' in img_entry
        assert 'encoded_size_bytes' in img_entry
    print(f"[✓] Manifest 验证通过")
    print(f"    图片总数: {manifest['summary']['total_images']}")
    print(f"    原始总大小: {manifest['summary']['total_original_size_human']}")
    print(f"    编码后总大小: {manifest['summary']['total_encoded_size_human']}")

    print("\n" + "-" * 60)
    print("测试 28: 批量嵌入为 ZIP 压缩包（保存到文件）")
    print("-" * 60)
    zip_path = os.path.join(test_dir, 'batch_images.zip')
    result_zip_path = Base64ImageService.batch_embed_to_zip(
        batch_images, output_path=zip_path,
        include_html=True, include_json=True, include_manifest=True,
        compress=False, html_title='ZIP 批量图库'
    )
    assert result_zip_path == zip_path, "返回路径不匹配"
    assert os.path.isfile(zip_path), "ZIP 文件未生成"
    zip_size = os.path.getsize(zip_path)
    assert zip_size > 0, "ZIP 文件为空"
    print(f"[✓] ZIP 压缩包生成成功")
    print(f"    路径: {zip_path}")
    print(f"    大小: {Base64ImageService._format_size(zip_size)}")

    print("\n" + "-" * 60)
    print("测试 29: 批量嵌入为 ZIP 压缩包（返回内存字节）")
    print("-" * 60)
    zip_bytes = Base64ImageService.batch_embed_to_zip(
        batch_images, output_path=None,
        include_html=True, include_json=True, include_manifest=True,
        compress=False
    )
    assert isinstance(zip_bytes, bytes), "返回类型应为 bytes"
    assert len(zip_bytes) > 0, "返回字节为空"
    assert zip_bytes[:2] == b'PK', "ZIP 文件头错误"
    print(f"[✓] ZIP 内存字节生成成功")
    print(f"    字节数: {len(zip_bytes)}")
    print(f"    文件头校验: 通过 (PK)")

    print("\n" + "-" * 60)
    print("测试 30: ZIP 压缩包内容完整性验证")
    print("-" * 60)
    import zipfile as zf
    with zf.ZipFile(zip_path, 'r') as zip_ref:
        zip_name_list = zip_ref.namelist()
        assert 'gallery.html' in zip_name_list, "缺少 gallery.html"
        assert 'images.json' in zip_name_list, "缺少 images.json"
        assert 'manifest.json' in zip_name_list, "缺少 manifest.json"
        print(f"[✓] ZIP 内文件列表验证通过")
        for name in zip_name_list:
            info = zip_ref.getinfo(name)
            print(f"    {name} ({info.file_size} 字节)")

    print("\n" + "-" * 60)
    print("测试 31: 从 ZIP 中反向提取并还原图片")
    print("-" * 60)
    extract_zip_dir = os.path.join(test_dir, 'extracted_zip')
    extract_result = Base64ImageService.extract_from_zip(
        zip_path, output_dir=extract_zip_dir
    )
    assert extract_result['manifest'] is not None, "Manifest 未提取"
    assert len(extract_result['extracted_files']) >= 3, "提取文件数不足"
    assert len(extract_result['restored_images']) == 3, "还原图片数量不匹配"
    for restored in extract_result['restored_images']:
        assert os.path.isfile(restored['path']), f"还原文件不存在: {restored['path']}"
        assert restored['size_bytes'] > 0, "还原文件为空"
    print(f"[✓] 从 ZIP 提取还原成功")
    print(f"    提取文件数: {len(extract_result['extracted_files'])}")
    print(f"    还原图片数: {len(extract_result['restored_images'])}")
    for restored in extract_result['restored_images']:
        print(f"    - {os.path.basename(restored['path'])} ({restored['size_bytes']} 字节)")

    print("\n" + "-" * 60)
    print("测试 32: 还原图片内容与原始一致")
    print("-" * 60)
    with open(test_image1, 'rb') as f:
        original1 = f.read()
    with open(test_image2, 'rb') as f:
        original2 = f.read()
    with open(large_image, 'rb') as f:
        original_large = f.read()
    original_list = [original1, original2, original_large]

    for idx, restored in enumerate(extract_result['restored_images']):
        with open(restored['path'], 'rb') as f:
            restored_bytes = f.read()
        assert restored_bytes == original_list[idx], f"图片 {idx} 还原后内容不一致"
    print(f"[✓] 所有 {len(extract_result['restored_images'])} 张图片还原后与原始完全一致")

    print("\n" + "-" * 60)
    print("测试 33: 批量嵌入 + 压缩模式")
    print("-" * 60)
    zip_compressed_path = os.path.join(test_dir, 'batch_compressed.zip')
    Base64ImageService.batch_embed_to_zip(
        batch_images, output_path=zip_compressed_path,
        include_html=False, include_json=True, include_manifest=True,
        compress=True, segmented=False
    )
    assert os.path.isfile(zip_compressed_path), "压缩模式 ZIP 未生成"

    with zf.ZipFile(zip_compressed_path, 'r') as zc:
        zc_files = zc.namelist()
        assert 'gallery.html' not in zc_files, "不应包含 HTML"
        assert 'images.json' in zc_files, "应包含 JSON"
        json_raw = zc.read('images.json').decode('utf-8')
        json_data = json.loads(json_raw)
        first_key = list(json_data.keys())[0]
        assert json_data[first_key]['data_url'].startswith('data:image/png;base64;zlib,'), \
            "压缩模式下应包含 zlib 标识"

    print(f"[✓] 压缩模式批量嵌入成功")
    print(f"    ZIP 大小: {Base64ImageService._format_size(os.path.getsize(zip_compressed_path))}")
    print(f"    压缩标识验证: 通过")

    print("\n" + "-" * 60)
    print("测试 34: 批量嵌入 + 分段存储模式")
    print("-" * 60)
    Base64ImageService.set_segment_length(50)
    zip_segmented_path = os.path.join(test_dir, 'batch_segmented.zip')
    Base64ImageService.batch_embed_to_zip(
        batch_images, output_path=zip_segmented_path,
        include_html=False, include_json=True, include_manifest=True,
        compress=False, segmented=True
    )
    assert os.path.isfile(zip_segmented_path), "分段模式 ZIP 未生成"

    with zf.ZipFile(zip_segmented_path, 'r') as zs:
        json_raw = zs.read('images.json').decode('utf-8')
        json_data = json.loads(json_raw)
        first_key = list(json_data.keys())[0]
        assert json_data[first_key]['segmented'] == True, "segmented 标记应为 True"
        assert 'data' in json_data[first_key], "应包含分段 data"
        assert 'segments' in json_data[first_key]['data'], "应包含 segments 列表"

    Base64ImageService.set_segment_length(Base64ImageService.DEFAULT_SEGMENT_LENGTH)
    print(f"[✓] 分段模式批量嵌入成功")
    print(f"    ZIP 大小: {Base64ImageService._format_size(os.path.getsize(zip_segmented_path))}")
    print(f"    分段数据验证: 通过")

    print("\n" + "-" * 60)
    print("测试 35: 空列表和不存在文件异常处理")
    print("-" * 60)
    try:
        Base64ImageService.batch_embed_to_zip([], output_path=os.path.join(test_dir, 'empty.zip'))
        assert False, "空列表应抛出 ValueError"
    except ValueError:
        print("[✓] 空列表正确抛出 ValueError")

    try:
        Base64ImageService.batch_embed_to_zip(
            [{'path': 'nonexistent.png', 'key': 'x'}],
            output_path=os.path.join(test_dir, 'bad.zip')
        )
        assert False, "不存在文件应抛出 FileNotFoundError"
    except FileNotFoundError:
        print("[✓] 不存在文件正确抛出 FileNotFoundError")

    print("\n" + "=" * 60)
    print(f"所有 {35} 项测试通过! ✓")
    print("=" * 60)
    print(f"\n测试输出目录: {test_dir}")
    print("\n生成的文件:")
    for root, dirs, files in os.walk(test_dir):
        for f in sorted(files):
            filepath = os.path.join(root, f)
            size = os.path.getsize(filepath)
            print(f"  {os.path.relpath(filepath, test_dir)} ({size} 字节)")


if __name__ == '__main__':
    run_tests()
