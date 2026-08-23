from uuid import uuid4

from lina_agent.domain.job_parser import parse_job_constraints
from lina_agent.domain.models import EducationLevel


def test_parse_job_constraints_extracts_values_with_source_offsets() -> None:
    description = (
        "工作地点：上海。面向 2027、2028 届毕业生，要求本科及以上学历，具备 3 年以上工作经验。"
    )

    result = parse_job_constraints(description, document_id=uuid4())

    assert result.constraints.graduation_years == {2027, 2028}
    assert result.constraints.minimum_education is EducationLevel.BACHELOR
    assert result.constraints.minimum_years_of_experience == 3
    assert result.constraints.locations == {"上海"}
    assert result.warnings == ()

    evidence = [
        *result.evidence.graduation_years,
        result.evidence.minimum_education,
        result.evidence.minimum_years_of_experience,
        *result.evidence.locations,
    ]
    for item in evidence:
        assert item is not None
        assert description[item.start_offset : item.end_offset] == item.text


def test_parse_job_constraints_does_not_infer_unstated_requirements() -> None:
    result = parse_job_constraints(
        "寻找热爱 Agent 工程、学习能力强的同学加入团队。",
        document_id=uuid4(),
    )

    assert not result.constraints.graduation_years
    assert result.constraints.minimum_education is None
    assert result.constraints.minimum_years_of_experience is None
    assert not result.constraints.locations
    assert result.warnings == ("未识别到明确的毕业年份、学历、经验或工作地点约束，请人工确认。",)


def test_parse_job_constraints_treats_zero_experience_as_explicit() -> None:
    result = parse_job_constraints("无需实习经历，接受 0 年工作经验。", document_id=uuid4())

    assert result.constraints.minimum_years_of_experience == 0
    assert result.warnings == ()


def test_parse_job_constraints_does_not_promote_preferences_to_requirements() -> None:
    result = parse_job_constraints(
        "硕士及以上学历优先，本科及以上学历即可。具有 3 年以上工作经验者优先。",
        document_id=uuid4(),
    )

    assert result.constraints.minimum_education is EducationLevel.BACHELOR
    assert result.constraints.minimum_years_of_experience is None
    assert result.evidence.minimum_education is not None
    assert result.evidence.minimum_education.text == "本科及以上学历"
    assert result.evidence.minimum_years_of_experience is None


def test_parse_job_constraints_ignores_preceding_preferences() -> None:
    result = parse_job_constraints(
        "优先考虑硕士及以上学历，优先考虑具有 3 年以上工作经验。",
        document_id=uuid4(),
    )

    assert result.constraints.minimum_education is None
    assert result.constraints.minimum_years_of_experience is None


def test_parse_job_constraints_ignores_punctuated_and_graduation_preferences() -> None:
    result = parse_job_constraints(
        "优先考虑：硕士及以上学历。3 年以上工作经验，优先考虑。2027 届优先，要求 2028 届。",
        document_id=uuid4(),
    )

    assert result.constraints.minimum_education is None
    assert result.constraints.minimum_years_of_experience is None
    assert result.constraints.graduation_years == {2028}


def test_parse_job_constraints_preserves_location_names_containing_conjunctions() -> None:
    result = parse_job_constraints("工作地点：和田。", document_id=uuid4())

    assert result.constraints.locations == {"和田"}

    qualified_result = parse_job_constraints("工作地点：新疆和田。", document_id=uuid4())

    assert qualified_result.constraints.locations == {"新疆和田"}


def test_parse_job_constraints_does_not_create_ambiguous_combined_location() -> None:
    result = parse_job_constraints("工作地点：北京和上海。", document_id=uuid4())

    assert not result.constraints.locations
    assert result.evidence.locations
    assert result.warnings == ("工作地点包含未可靠拆分的并列表达，请人工确认。",)
