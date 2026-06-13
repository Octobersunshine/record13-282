import base64
import json
import re
import os
import zlib
import warnings
import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Iterator, Any


class Base64ImageService:
    MIME_TYPE_MAP = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
    }

    DATA_URL_PATTERN = re.compile(
        r'data:(image/[\w+\-.]+);base64,([A-Za-z0-9+/=]+)',
        re.IGNORECASE
    )

    HTML_IMG_PATTERN = re.compile(
        r'<img[^>]+src=["\'](data:image/[^"\']+)["\'][^>]*>',
        re.IGNORECASE
    )

    COMPRESSED_DATA_URL_PATTERN = re.compile(
        r'data:(image/[\w+\-.]+);base64;zlib,([A-Za-z0-9+/=]+)',
        re.IGNORECASE
    )

    DEFAULT_WARN_SIZE = 1 * 1024 * 1024
    DEFAULT_CHUNK_SIZE = 64 * 1024
    DEFAULT_SEGMENT_LENGTH = 80

    warn_size = DEFAULT_WARN_SIZE
    chunk_size = DEFAULT_CHUNK_SIZE
    segment_length = DEFAULT_SEGMENT_LENGTH
    enable_warnings = True

    @classmethod
    def _get_mime_type(cls, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext not in cls.MIME_TYPE_MAP:
            raise ValueError(f"不支持的图片格式: {ext}")
        return cls.MIME_TYPE_MAP[ext]

    @classmethod
    def _get_extension_from_mime(cls, mime_type: str) -> str:
        mime_lower = mime_type.lower()
        for ext, mime in cls.MIME_TYPE_MAP.items():
            if mime == mime_lower:
                return ext
        return '.png'

    @classmethod
    def _format_size(cls, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    @classmethod
    def _check_file_size(cls, file_path: str) -> Tuple[int, bool]:
        file_size = os.path.getsize(file_path)
        is_large = file_size > cls.warn_size
        if is_large and cls.enable_warnings:
            base64_size = int(file_size * 4 / 3)
            warnings.warn(
                f"图片文件较大 ({cls._format_size(file_size)})，"
                f"Base64 编码后约 {cls._format_size(base64_size)}，"
                f"可能导致 JSON/HTML 体积过大。建议考虑："
                f"1) 使用 compress=True 启用压缩；"
                f"2) 使用 segmented=True 分段存储；"
                f"3) 使用流式编码 encode_file_streaming()。",
                UserWarning,
                stacklevel=3
            )
        return file_size, is_large

    @classmethod
    def get_file_info(cls, image_path: str) -> Dict[str, Any]:
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        file_size = os.path.getsize(image_path)
        mime_type = cls._get_mime_type(image_path)
        base64_estimated_size = int(file_size * 4 / 3)
        is_large = file_size > cls.warn_size

        return {
            'path': image_path,
            'filename': os.path.basename(image_path),
            'size_bytes': file_size,
            'size_human': cls._format_size(file_size),
            'mime_type': mime_type,
            'base64_estimated_bytes': base64_estimated_size,
            'base64_estimated_human': cls._format_size(base64_estimated_size),
            'is_large': is_large,
            'warn_threshold': cls.warn_size,
            'warn_threshold_human': cls._format_size(cls.warn_size),
        }

    @classmethod
    def set_warn_size(cls, size_bytes: int) -> None:
        cls.warn_size = size_bytes

    @classmethod
    def set_chunk_size(cls, size_bytes: int) -> None:
        cls.chunk_size = size_bytes

    @classmethod
    def set_segment_length(cls, length: int) -> None:
        cls.segment_length = length

    @classmethod
    def set_warnings_enabled(cls, enabled: bool) -> None:
        cls.enable_warnings = enabled

    @classmethod
    def encode_file(cls, image_path: str, compress: bool = False,
                    check_size: bool = True) -> str:
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        mime_type = cls._get_mime_type(image_path)

        if check_size:
            cls._check_file_size(image_path)

        with open(image_path, 'rb') as f:
            image_data = f.read()

        if compress:
            image_data = zlib.compress(image_data)
            base64_data = base64.b64encode(image_data).decode('utf-8')
            return f"data:{mime_type};base64;zlib,{base64_data}"

        base64_data = base64.b64encode(image_data).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"

    @classmethod
    def encode_file_streaming(cls, image_path: str,
                              compress: bool = False) -> Iterator[str]:
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        mime_type = cls._get_mime_type(image_path)
        file_size, is_large = cls._check_file_size(image_path)

        header = f"data:{mime_type};base64{';zlib' if compress else ''},"
        yield header

        if compress:
            compressor = zlib.compressobj()
            leftover = b''
            with open(image_path, 'rb') as f:
                while True:
                    chunk = f.read(cls.chunk_size)
                    if not chunk:
                        break
                    compressed = compressor.compress(chunk)
                    if compressed:
                        leftover += compressed
                    while len(leftover) >= 3:
                        take = (len(leftover) // 3) * 3
                        encode_part = leftover[:take]
                        leftover = leftover[take:]
                        yield base64.b64encode(encode_part).decode('utf-8')
            remaining = compressor.flush()
            if remaining:
                leftover += remaining
            if leftover:
                yield base64.b64encode(leftover).decode('utf-8')
        else:
            leftover = b''
            with open(image_path, 'rb') as f:
                while True:
                    chunk = f.read(cls.chunk_size)
                    if not chunk:
                        break
                    leftover += chunk
                    while len(leftover) >= 3:
                        take = (len(leftover) // 3) * 3
                        encode_part = leftover[:take]
                        leftover = leftover[take:]
                        yield base64.b64encode(encode_part).decode('utf-8')
            if leftover:
                yield base64.b64encode(leftover).decode('utf-8')

    @classmethod
    def encode_file_segmented(cls, image_path: str,
                              compress: bool = False) -> Dict[str, Any]:
        data_url = cls.encode_file(image_path, compress=compress, check_size=True)
        comma_idx = data_url.index(',')
        header = data_url[:comma_idx + 1]
        base64_data = data_url[comma_idx + 1:]

        segments = []
        for i in range(0, len(base64_data), cls.segment_length):
            segments.append(base64_data[i:i + cls.segment_length])

        return {
            'mime_type': cls._get_mime_type(image_path),
            'compressed': compress,
            'total_segments': len(segments),
            'segment_length': cls.segment_length,
            'total_size_bytes': os.path.getsize(image_path),
            'header': header,
            'segments': segments,
        }

    @classmethod
    def reassemble_segmented(cls, segmented_data: Dict[str, Any]) -> str:
        header = segmented_data.get('header', '')
        segments = segmented_data.get('segments', [])
        if not header or not segments:
            raise ValueError("分段数据格式无效，缺少 header 或 segments")
        return header + ''.join(segments)

    @classmethod
    def encode_bytes(cls, image_bytes: bytes, mime_type: str = 'image/png',
                     compress: bool = False) -> str:
        if not isinstance(image_bytes, (bytes, bytearray)):
            raise TypeError("image_bytes 必须是 bytes 类型")

        if compress:
            compressed = zlib.compress(bytes(image_bytes))
            base64_data = base64.b64encode(compressed).decode('utf-8')
            return f"data:{mime_type};base64;zlib,{base64_data}"

        base64_data = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"

    @classmethod
    def decode_to_bytes(cls, data_url: str) -> Tuple[bytes, str]:
        compressed_match = cls.COMPRESSED_DATA_URL_PATTERN.search(data_url)
        if compressed_match:
            mime_type = compressed_match.group(1)
            base64_data = compressed_match.group(2)
            compressed_bytes = base64.b64decode(base64_data)
            image_bytes = zlib.decompress(compressed_bytes)
            return image_bytes, mime_type

        match = cls.DATA_URL_PATTERN.search(data_url)
        if not match:
            raise ValueError("无效的 DataURL 格式")

        mime_type = match.group(1)
        base64_data = match.group(2)
        image_bytes = base64.b64decode(base64_data)
        return image_bytes, mime_type

    @classmethod
    def decode_to_file(cls, data_url: str, output_path: str) -> str:
        image_bytes, mime_type = cls.decode_to_bytes(data_url)

        if not Path(output_path).suffix:
            ext = cls._get_extension_from_mime(mime_type)
            output_path = output_path + ext

        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)

        with open(output_path, 'wb') as f:
            f.write(image_bytes)

        return output_path

    @classmethod
    def embed_in_html(cls, image_path: str, alt_text: str = 'image',
                      width: Optional[str] = None,
                      height: Optional[str] = None,
                      compress: bool = False) -> str:
        data_url = cls.encode_file(image_path, compress=compress)

        attrs = [f'src="{data_url}"', f'alt="{alt_text}"']
        if width:
            attrs.append(f'width="{width}"')
        if height:
            attrs.append(f'height="{height}"')

        return f"<img {' '.join(attrs)}>"

    @classmethod
    def create_html_page(cls, images: List[Dict[str, str]],
                         title: str = 'Base64 Images',
                         output_path: Optional[str] = None) -> str:
        img_tags = []
        for img in images:
            path = img.get('path', '')
            alt = img.get('alt', 'image')
            width = img.get('width')
            height = img.get('height')
            compress = img.get('compress', False)
            img_tag = cls.embed_in_html(path, alt, width, height, compress)
            img_tags.append(f'<div class="image-item">{img_tag}</div>')

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        .image-item {{ margin: 20px 0; padding: 10px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .image-item img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {''.join(img_tags)}
</body>
</html>"""

        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)

        return html

    @classmethod
    def embed_in_json(cls, image_path: str, key: str = 'image',
                      compress: bool = False,
                      segmented: bool = False) -> Dict:
        if segmented:
            segmented_data = cls.encode_file_segmented(image_path, compress=compress)
            return {key: segmented_data}
        data_url = cls.encode_file(image_path, compress=compress)
        return {key: data_url}

    @classmethod
    def create_json_payload(cls, images: List[Dict[str, Any]],
                            output_path: Optional[str] = None,
                            compress: bool = False,
                            segmented: bool = False) -> Dict:
        payload = {}
        for idx, img in enumerate(images):
            path = img.get('path', '')
            key = img.get('key', f'image_{idx}')
            img_compress = img.get('compress', compress)
            img_segmented = img.get('segmented', segmented)

            if img_segmented:
                segmented_data = cls.encode_file_segmented(path, compress=img_compress)
                payload[key] = {
                    'segmented': True,
                    'data': segmented_data,
                    'filename': os.path.basename(path),
                    'size_bytes': os.path.getsize(path)
                }
            else:
                data_url = cls.encode_file(path, compress=img_compress)
                payload[key] = {
                    'segmented': False,
                    'data_url': data_url,
                    'filename': os.path.basename(path),
                    'size_bytes': os.path.getsize(path)
                }

        if output_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

        return payload

    @classmethod
    def extract_from_html(cls, html_content: str) -> List[Dict[str, str]]:
        matches = cls.HTML_IMG_PATTERN.findall(html_content)
        results = []
        for data_url in matches:
            image_bytes, mime_type = cls.decode_to_bytes(data_url)
            results.append({
                'data_url': data_url,
                'mime_type': mime_type,
                'size_bytes': len(image_bytes)
            })
        return results

    @classmethod
    def extract_from_json(cls, json_data: Union[str, Dict]) -> List[Dict[str, Any]]:
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        results = []

        def _is_segmented_dict(obj):
            return (isinstance(obj, dict)
                    and 'header' in obj
                    and 'segments' in obj
                    and isinstance(obj['segments'], list)
                    and isinstance(obj['header'], str)
                    and obj['header'].startswith('data:image/'))

        def _process_segmented(obj, path):
            try:
                data_url = cls.reassemble_segmented(obj)
                image_bytes, mime_type = cls.decode_to_bytes(data_url)
                results.append({
                    'path': path,
                    'data_url': data_url,
                    'mime_type': mime_type,
                    'size_bytes': len(image_bytes),
                    'segmented': True,
                    'total_segments': len(obj['segments']),
                })
            except (ValueError, KeyError):
                pass

        def _find_data_urls(obj, path=''):
            if isinstance(obj, dict):
                if _is_segmented_dict(obj):
                    _process_segmented(obj, path)
                    return

                if obj.get('segmented') is True and 'data' in obj:
                    data_obj = obj['data']
                    if _is_segmented_dict(data_obj):
                        _process_segmented(data_obj, path)
                        return

                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, str) and value.startswith('data:image/'):
                        try:
                            image_bytes, mime_type = cls.decode_to_bytes(value)
                            results.append({
                                'path': current_path,
                                'data_url': value,
                                'mime_type': mime_type,
                                'size_bytes': len(image_bytes),
                                'segmented': False,
                            })
                        except ValueError:
                            pass
                    else:
                        _find_data_urls(value, current_path)
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    _find_data_urls(item, f"{path}[{idx}]")

        _find_data_urls(data)
        return results

    @classmethod
    def extract_and_save(cls, source: str, source_type: str = 'html',
                         output_dir: str = 'extracted_images') -> List[str]:
        if source_type == 'html':
            extracted = cls.extract_from_html(source)
        elif source_type == 'json':
            extracted = cls.extract_from_json(source)
        else:
            raise ValueError(f"不支持的源类型: {source_type}，请使用 'html' 或 'json'")

        os.makedirs(output_dir, exist_ok=True)
        saved_files = []

        for idx, item in enumerate(extracted):
            ext = cls._get_extension_from_mime(item['mime_type'])
            filename = f"image_{idx}{ext}"
            filepath = os.path.join(output_dir, filename)
            cls.decode_to_file(item['data_url'], filepath)
            saved_files.append(filepath)

        return saved_files
