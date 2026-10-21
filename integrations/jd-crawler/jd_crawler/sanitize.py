"""入库前脱敏:屏蔽 JD 正文中可能出现的个人联系方式。

只针对**公开 JD 文本**里偶然出现的手机号 / 邮箱 / 微信号做占位替换,
不采集、不还原。规则宁可误伤(lorem 数字串)也不漏过。
"""

from __future__ import annotations

import re

# 中国大陆手机号(连写或 3-4-4 分隔)
_PHONE_RE = re.compile(r"(?<!\d)(?:1[3-9]\d{9}|1[3-9]\d[ -]\d{4}[ -]\d{4})(?!\d)")
# 邮箱
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 微信号(“微信/微信号/WeChat/wx：xxx” 形式)
_WECHAT_RE = re.compile(
    r"(?:微信|微信号|wechat|weixin|wx)\s*[:：]?\s*[A-Za-z][A-Za-z0-9_-]{5,19}",
    re.IGNORECASE,
)
# 常见座机/QQ 号(宽松处理,避免出现联系方式)
_QQ_RE = re.compile(r"(?:QQ|qq)\s*[:：]?\s*[1-9]\d{4,10}(?!\d)")


def mask_contacts(text: str | None) -> str:
    """返回脱敏后的文本;对 None/空串安全。"""
    if not text:
        return ""
    out = _EMAIL_RE.sub("[EMAIL]", text)
    out = _PHONE_RE.sub("[PHONE]", out)
    out = _WECHAT_RE.sub("[WECHAT]", out)
    out = _QQ_RE.sub("[QQ]", out)
    return out
