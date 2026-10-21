import pytest

from agents.assessment.resume_parser import ResumeParsingAgent


def test_sections_stop_at_real_resume_headings_and_ignore_certificates_as_skills():
    result = ResumeParsingAgent().parse(
        """
        专业技能
        Python、SQL、数据分析
        技能证书
        CET-6、普通话二级乙等、C1机动车驾驶证
        荣誉与奖项
        Python技能比赛一等奖
        项目经历
        """,
        use_remote=False,
    )

    names = {item["name"] for item in result["skills"]}
    assert {"Python", "SQL", "数据分析"} <= names
    assert "CET-6" not in names
    assert result["certifications"]


def test_project_headers_support_number_date_role_and_pipe_forms():
    result = ResumeParsingAgent().parse(
        """
        项目经历
        2025.09—2026.01 房屋租赁管理系统 项目负责人
        使用 Java 完成系统开发。
        （一）贷款风险预测（分类问题） 2023.02-2023.09
        使用 Python 完成建模。
        项目3｜知识问答工作台 V2｜2024.01-2024.06｜核心开发
        负责检索服务开发。
        """,
        use_remote=False,
    )

    names = [item["name"] for item in result["projects"]]
    assert "房屋租赁管理系统" in names
    assert "贷款风险预测（分类问题）" in names
    assert "知识问答工作台 V2" in names
    assert all("2025" not in name and "项目负责人" not in name for name in names)


def test_experience_does_not_use_phone_birth_year_or_education_dates():
    parser = ResumeParsingAgent()
    text = """
    手机：13812345678 出生年月：2001.08
    教育经历
    2021.09-2025.06 某大学 本科
    工作经历
    2023.07-2025.06 某公司 软件工程师
    工作经验：2年
    """

    result = parser.parse(text, use_remote=False)
    assert result["experience_years"] == 2.0
    assert result["work_history"] == [{"start": "2023.07", "end": "2025.06", "evidence": "某公司 软件工程师"}]


def test_experience_without_explicit_work_signal_is_empty():
    result = ResumeParsingAgent().parse(
        "出生年月：2001.08\n教育经历\n2021.09-2025.06 某大学 本科",
        use_remote=False,
    )

    assert result["experience_years"] is None
    assert result["work_history"] == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("计算机科学本科，3 年 Java 后端开发经验。", 3.0),
        ("具有 2.5 年 Python 开发经验。", 2.5),
        ("5 years of backend engineering experience.", 5.0),
        ("计算机本科，0 年工作经验，应届毕业生。", 0.0),
        ("2020 年毕业，暂无工作经验。", None),
        ("本科 4 年。项目经历：课程网站开发。", None),
        ("3 年前毕业\n工作经历\n暂无", None),
    ],
)
def test_experience_accepts_duration_before_role_without_using_unrelated_dates(text, expected):
    result = ResumeParsingAgent().parse(text, use_remote=False)

    assert result["experience_years"] == expected


def test_education_location_and_certification_require_observable_context():
    result = ResumeParsingAgent().parse(
        """
        求职意向：数据分析；期望城市：宁波
        教育背景
        某大学 本科
        某大学 硕士
        证书及荣誉
        大学英语六级证书；普通话二级甲等；驾驶证
        """,
        use_remote=False,
    )

    assert result["education"] == "硕士"
    assert result["preferred_locations"] == ["宁波"]
    assert "大学英语六级证书" in result["certifications"]
    assert any("驾驶证" in item for item in result["certifications"])
