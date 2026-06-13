import base64
import json
import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


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
    def encode_file(cls, image_path: str) -> str:
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        mime_type = cls._get_mime_type(image_path)

        with open(image_path, 'rb') as f:
            image_data = f.read()

        base64_data = base64.b64encode(image_data).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"

    @classmethod
    def encode_bytes(cls, image_bytes: bytes, mime_type: str = 'image/png') -> str:
        if not isinstance(image_bytes, (bytes, bytearray)):
            raise TypeError("image_bytes 必须是 bytes 类型")

        base64_data = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"

    @classmethod
    def decode_to_bytes(cls, data_url: str) -> Tuple[bytes, str]:
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
                      height: Optional[str] = None) -> str:
        data_url = cls.encode_file(image_path)

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
            img_tag = cls.embed_in_html(path, alt, width, height)
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
    def embed_in_json(cls, image_path: str, key: str = 'image') -> Dict:
        data_url = cls.encode_file(image_path)
        return {key: data_url}

    @classmethod
    def create_json_payload(cls, images: List[Dict[str, str]],
                            output_path: Optional[str] = None) -> Dict:
        payload = {}
        for idx, img in enumerate(images):
            path = img.get('path', '')
            key = img.get('key', f'image_{idx}')
            data_url = cls.encode_file(path)
            payload[key] = {
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
    def extract_from_json(cls, json_data: Union[str, Dict]) -> List[Dict[str, str]]:
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        results = []

        def _find_data_urls(obj, path=''):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, str) and value.startswith('data:image/'):
                        try:
                            image_bytes, mime_type = cls.decode_to_bytes(value)
                            results.append({
                                'path': current_path,
                                'data_url': value,
                                'mime_type': mime_type,
                                'size_bytes': len(image_bytes)
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
