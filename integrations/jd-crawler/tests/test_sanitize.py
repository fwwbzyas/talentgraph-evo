from jd_crawler.sanitize import mask_contacts


def test_mask_phone():
    assert mask_contacts("联系电话13812345678张经理") == "联系电话[PHONE]张经理"
    assert mask_contacts("手机: 138-1234-5678") == "手机: [PHONE]"


def test_mask_email():
    assert mask_contacts("简历发至 hr.zhang@example.com 谢谢") == "简历发至 [EMAIL] 谢谢"


def test_mask_wechat_and_qq():
    assert mask_contacts("微信: abcdef_2020 详聊") == "[WECHAT] 详聊"
    assert mask_contacts("WeChat：abcdef1") == "[WECHAT]"
    assert mask_contacts("QQ: 123456789") == "[QQ]"


def test_none_and_empty():
    assert mask_contacts(None) == ""
    assert mask_contacts("") == ""


def test_normal_text_untouched():
    s = "负责后端服务开发,熟悉 Python / Go,3-5 年经验。"
    assert mask_contacts(s) == s
