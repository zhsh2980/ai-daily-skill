"""
钉钉通知模块
发送 AI 日报到钉钉群
"""
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
from typing import Optional, Dict, Any

from src.config import (
    DINGTALK_WEBHOOK_URL,
    DINGTALK_SECRET,
    ENABLE_DINGTALK,
    GITHUB_PAGES_URL
)


class DingTalkNotifier:
    """钉钉机器人通知器"""

    def __init__(self, webhook_url: str = None, secret: str = None):
        """
        初始化钉钉通知器

        Args:
            webhook_url: Webhook URL，以 https://oapi.dingtalk.com/robot/send?access_token= 开头
            secret: 加签密钥，以 SEC 开头
        """
        self.webhook_url = webhook_url or DINGTALK_WEBHOOK_URL
        self.secret = secret or DINGTALK_SECRET

    def _generate_sign(self) -> tuple:
        """
        生成加签参数

        Returns:
            (timestamp, sign) 元组
        """
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{self.secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(
            secret_enc,
            string_to_sign_enc,
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return timestamp, sign

    def _get_webhook_url(self) -> str:
        """获取带签名的 Webhook URL"""
        if not self.secret:
            return self.webhook_url
        timestamp, sign = self._generate_sign()
        return f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"

    def _is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.webhook_url and ENABLE_DINGTALK)

    def send_markdown(self, title: str, content: str) -> bool:
        """
        发送 Markdown 消息

        Args:
            title: 消息标题（会在通知中显示）
            content: Markdown 格式的消息内容

        Returns:
            是否发送成功
        """
        if not self._is_configured():
            return False

        url = self._get_webhook_url()
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            }
        }

        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            if result.get("errcode") == 0:
                print(f"✅ 钉钉消息发送成功: {title}")
                return True
            else:
                print(f"❌ 钉钉消息发送失败: {result.get('errmsg')}")
                return False
        except Exception as e:
            print(f"❌ 钉钉消息发送异常: {e}")
            return False

    def send_daily_report(self, result: Dict[str, Any], page_url: str) -> bool:
        """
        发送 AI 日报

        Args:
            result: AI 分析结果字典
            page_url: 日报页面 URL

        Returns:
            是否发送成功
        """
        date = result.get("date", "")
        summary = result.get("summary", [])
        categories = result.get("categories", [])
        keywords = result.get("keywords", [])

        # 统计各分类资讯数
        stats = []
        total = 0
        for cat in categories:
            count = len(cat.get("items", []))
            total += count
            if count > 0:
                stats.append(f"- {cat.get('icon', '')} {cat.get('name', '')}: {count} 条")

        # 构建 Markdown 内容
        content = f"## 📰 AI Daily · {date}\n\n"
        
        # 今日摘要
        content += "### 📌 今日核心摘要\n"
        for s in summary[:5]:
            content += f"- {s}\n"
        
        # 资讯统计
        if stats:
            content += f"\n### 📊 资讯统计（共 {total} 条）\n"
            content += "\n".join(stats)
        
        # 关键词
        if keywords:
            content += f"\n\n### 🏷️ 关键词\n"
            content += " · ".join(keywords[:8])

        # 详情链接
        content += f"\n\n---\n\n[🔗 点击查看完整日报]({page_url})"

        title = f"📰 AI Daily · {date}"
        return self.send_markdown(title, content)

    def send_error(self, date: str, error: str) -> bool:
        """
        发送错误通知

        Args:
            date: 目标日期
            error: 错误信息

        Returns:
            是否发送成功
        """
        content = f"## ❌ AI Daily 生成失败\n\n"
        content += f"**目标日期**: {date}\n\n"
        content += f"**错误信息**: {error}\n\n"
        content += "请检查 GitHub Actions 日志获取详细信息。"

        return self.send_markdown(f"❌ AI Daily 生成失败 - {date}", content)


# 便捷函数
def send_dingtalk_report(result: Dict[str, Any], date: str) -> bool:
    """便捷函数：发送日报到钉钉"""
    notifier = DingTalkNotifier()
    if not notifier._is_configured():
        return False
    
    # 构建页面 URL
    base_url = GITHUB_PAGES_URL or "https://zhsh2980.github.io/ai-daily-skill"
    page_url = f"{base_url.rstrip('/')}/{date}.html"
    
    return notifier.send_daily_report(result, page_url)
