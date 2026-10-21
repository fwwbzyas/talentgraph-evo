from agents.assessment.resume_parser import ResumeParsingAgent


def _projects(text: str):
    return ResumeParsingAgent().parse(text, use_remote=False)["projects"]


def test_project_name_version_suffixes_are_valid():
    parser = ResumeParsingAgent()

    for name in (
        "知识问答工作台·第1期",
        "知识问答工作台·第十二期",
        "知识问答工作台 V2",
        "知识问答工作台 v1.2",
        "知识问答工作台2025版",
        "知识问答工作台·二期",
    ):
        assert parser._looks_like_project_name(name) is True


def test_pipe_project_headings_are_extracted_only_from_project_section():
    result = _projects(
        """
        优势
        项目1｜知识问答工作台·第1期｜2023.07-2024.02｜核心开发
        负责把优势描述写得清晰。

        项目经历
        项目1｜知识问答工作台·第1期｜2023.07-2024.02｜核心开发
        技术动作：完成检索、重排和上线验证。量化结果：延迟下降20%。
        项目2｜售后助手 V2｜2024.01-2024.06｜开发
        技术动作：建设服务并完成灰度发布。
        """
    )

    assert [item["name"] for item in result] == ["知识问答工作台·第1期", "售后助手 V2"]
    assert all(item["verification_status"] == "supported" for item in result)


def test_colon_project_forms_keep_original_evidence():
    result = _projects(
        "技能：Python\n项目：知识问答工作台2025版。负责检索服务开发，延迟下降20%。\n"
        "项目名称：售后助手·二期。负责接口建设，命中率提升10%。"
    )

    assert [item["name"] for item in result] == ["知识问答工作台2025版", "售后助手·二期"]
    assert all(item["name"].split("·")[0] in item["evidence"] for item in result)


def test_responsibility_and_advantage_sentences_are_not_projects():
    result = _projects(
        """
        工作经历：负责知识问答工作台项目的方案拆解、接口优化和上线交付。
        优势：擅长售后助手服务建设，能够推动跨团队协作。
        """
    )

    assert result == []
