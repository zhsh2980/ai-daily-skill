"""
图片生成模块
使用 Firefly Card API 将 Markdown 内容转换为精美图片
"""
import os
import base64
import requests
from typing import Dict, Any, Optional
from pathlib import Path

from src.config import (
    FIREFLY_API_URL,
    FIREFLY_API_KEY,
    FIREFLY_DEFAULT_CONFIG,
    ENABLE_IMAGE_GENERATION,
    OUTPUT_DIR
)


class ImageGenerator:
    """Firefly Card API 图片生成器"""

    # 图片配置常量
    DEFAULT_WIDTH = 400
    MIN_HEIGHT = 400
    MAX_HEIGHT = 1200
    BASE_HEIGHT = 150  # 标题和日期等固定部分的高度
    LINE_HEIGHT = 28   # 每行内容大约高度

    def __init__(self, api_url: str = None, api_key: str = None):
        """
        初始化图片生成器

        Args:
            api_url: Firefly API 地址
            api_key: API 密钥（如果需要）
        """
        self.api_url = api_url or FIREFLY_API_URL
        self.api_key = api_key or FIREFLY_API_KEY
        self.default_config = FIREFLY_DEFAULT_CONFIG.copy()
        self.enabled = ENABLE_IMAGE_GENERATION

    def _calculate_height(self, content: str, width: int = DEFAULT_WIDTH) -> int:
        """
        根据内容长度计算图片高度

        Args:
            content: Markdown 内容
            width: 图片宽度

        Returns:
            计算后的高度
        """
        # 统计内容行数（包括标题、列表项等）
        lines = content.split('\n')
        content_lines = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Markdown 标题占用更多高度
            if line.startswith('# '):
                content_lines += 2
            elif line.startswith('## '):
                content_lines += 1.8
            elif line.startswith('### '):
                content_lines += 1.5
            # 列表项
            elif line.startswith('- ') or line.startswith('* '):
                content_lines += 1
            # 粗体内容
            elif line.startswith('**'):
                content_lines += 1
            # 普通内容行
            elif line:
                content_lines += 1

        # 计算高度
        calculated_height = int(self.BASE_HEIGHT + content_lines * self.LINE_HEIGHT)

        # 限制在最小和最大高度之间
        height = max(self.MIN_HEIGHT, min(calculated_height, self.MAX_HEIGHT))

        # 打印调试信息
        print(f"   内容行数: {int(content_lines)}, 计算高度: {calculated_height}, 最终高度: {height}")

        return height

    def generate(
        self,
        markdown_content: str,
        output_path: str = None,
        custom_config: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        生成图片

        Args:
            markdown_content: Markdown 格式的内容
            output_path: 图片保存路径，默认为 docs/images/{date}.png
            custom_config: 自定义配置，会与默认配置合并

        Returns:
            成功返回图片保存路径，失败返回 None
        """
        if not self.enabled:
            print("   图片生成功能未启用，跳过")
            return None

        if not markdown_content or not markdown_content.strip():
            print("   内容为空，跳过图片生成")
            return None

        # 构建请求数据
        request_data = self.default_config.copy()
        if custom_config:
            request_data.update(custom_config)
        request_data["content"] = markdown_content

        # 根据内容动态计算高度（如果用户没有自定义高度）
        if custom_config and "height" in custom_config:
            height = custom_config["height"]
        else:
            height = self._calculate_height(markdown_content)
            request_data["height"] = height

        # 根据高度动态调整 ratio（保持比例）
        # 计算最接近的标准比例
        width = request_data.get("width", self.DEFAULT_WIDTH)
        ratio_wh = width / height
        if ratio_wh > 0.8:
            request_data["ratio"] = "1:1"
        elif ratio_wh > 0.6:
            request_data["ratio"] = "3:4"
        elif ratio_wh > 0.45:
            request_data["ratio"] = "9:16"
        else:
            request_data["ratio"] = "9:21"

        print(f"   图片尺寸: {width}x{height}, 比例: {request_data['ratio']}")

        # 如果有 API Key，添加到请求头
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            print(f"   正在调用 Firefly API 生成图片...")
            print(f"   API URL: {self.api_url}")

            response = requests.post(
                self.api_url,
                json=request_data,
                headers=headers,
                timeout=60
            )

            # 检查响应状态
            response.raise_for_status()

            # 检查 Content-Type
            content_type = response.headers.get('Content-Type', '')

            # 如果直接返回二进制图片流
            if 'image/' in content_type:
                image_bytes = response.content

                # 确定保存路径
                if not output_path:
                    output_dir = Path(OUTPUT_DIR) / "images"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    # 使用日期作为文件名
                    from datetime import datetime
                    date_str = datetime.now().strftime("%Y-%m-%d")
                    output_path = str(output_dir / f"{date_str}.png")

                # 保存图片
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(image_bytes)

                print(f"   图片已保存: {output_path}")
                print(f"   文件大小: {len(image_bytes)} bytes")
                return output_path

            # 如果返回 JSON（兼容其他可能的响应格式）
            else:
                result = response.json()

                # API 返回的数据可能是 base64 编码的图片，或者是图片 URL
                if "data" in result:
                    # 假设返回的是 base64 编码的图片
                    image_data = result["data"]

                    # 如果是 URL，直接返回
                    if isinstance(image_data, str) and image_data.startswith("http"):
                        print(f"   图片 URL: {image_data}")
                        return image_data

                    # 如果是 base64，解码并保存
                    if isinstance(image_data, str):
                        # 处理可能的 data URL 前缀
                        if image_data.startswith("data:image/"):
                            image_data = image_data.split(",", 1)[1]

                        image_bytes = base64.b64decode(image_data)

                        # 确定保存路径
                        if not output_path:
                            output_dir = Path(OUTPUT_DIR) / "images"
                            output_dir.mkdir(parents=True, exist_ok=True)
                            output_path = str(output_dir / "daily-card.png")

                        # 保存图片
                        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(image_bytes)

                        print(f"   图片已保存: {output_path}")
                        return output_path

                # 如果响应中有 imageUrl 字段
                if "imageUrl" in result:
                    print(f"   图片 URL: {result['imageUrl']}")
                    return result["imageUrl"]

                # 如果响应中有 url 字段
                if "url" in result:
                    print(f"   图片 URL: {result['url']}")
                    return result["url"]

                print(f"   响应 Content-Type: {content_type}")
                print(f"   响应内容: {result}")
                print("   无法从响应中提取图片数据")
                return None

        except requests.exceptions.RequestException as e:
            print(f"   API 请求失败: {e}")
            return None
        except Exception as e:
            print(f"   图片生成失败: {e}")
            return None

    def generate_from_analysis_result(
        self,
        analysis_result: Dict[str, Any],
        output_path: str = None
    ) -> Optional[str]:
        """
        从分析结果生成 Markdown 并转换为图片

        Args:
            analysis_result: Claude 分析结果
            output_path: 图片保存路径

        Returns:
            成功返回图片路径，失败返回 None
        """
        # 构建精简的 Markdown 内容（适合卡片显示）
        markdown = self._build_card_markdown(analysis_result)

        return self.generate(markdown, output_path)

    def _build_card_markdown(self, result: Dict[str, Any]) -> str:
        """
        构建适合卡片显示的精简 Markdown

        Args:
            result: 分析结果

        Returns:
            Markdown 格式的字符串
        """
        date = result.get("date", "")
        summary = result.get("summary", [])
        categories = result.get("categories", [])
        keywords = result.get("keywords", [])

        # 格式化日期
        try:
            from datetime import datetime
            dt = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = f"{dt.year}年{dt.month}月{dt.day}日"
        except:
            formatted_date = date

        # 构建标题
        lines = [f"# AI Daily\n## {formatted_date}\n"]

        # 核心摘要
        if summary:
            lines.append("### 核心摘要")
            for item in summary[:5]:  # 最多 5 条
                lines.append(f"- {item}")
            lines.append("")

        # 分类资讯
        for cat in categories:
            if not cat.get("items"):
                continue

            cat_name = cat.get("name", "")
            cat_items = cat.get("items", [])

            lines.append(f"### {cat_name}")
            for item in cat_items[:3]:  # 每个分类最多 3 条
                title = item.get("title", "")
                lines.append(f"**{title}**")
            lines.append("")

        # 关键词
        if keywords:
            lines.append(f"{' '.join(['#' + kw for kw in keywords[:8]])}")

        return "\n".join(lines)


def generate_card_image(
    markdown_content: str,
    output_path: str = None
) -> Optional[str]:
    """
    便捷函数：生成卡片图片

    Args:
        markdown_content: Markdown 内容
        output_path: 输出路径

    Returns:
        图片路径或 URL
    """
    generator = ImageGenerator()
    return generator.generate(markdown_content, output_path)


def generate_card_from_analysis(
    analysis_result: Dict[str, Any],
    output_path: str = None
) -> Optional[str]:
    """
    便捷函数：从分析结果生成卡片图片

    Args:
        analysis_result: 分析结果
        output_path: 输出路径

    Returns:
        图片路径或 URL
    """
    generator = ImageGenerator()
    return generator.generate_from_analysis_result(analysis_result, output_path)
