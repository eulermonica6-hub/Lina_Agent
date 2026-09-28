from datetime import UTC, datetime

from lina_agent.domain.job_discovery import (
    CompanyPool,
    JobLead,
    JobSearchRequest,
    JobSourceResult,
    JobSourceStatus,
    JobType,
    JobVerificationStatus,
)

_CAPTURED_AT = datetime(2026, 9, 28, tzinfo=UTC)
_SOURCE_ID = "verified-snapshot-2026-09-28"


class VerifiedSnapshotJobSource:
    source_id = _SOURCE_ID

    async def search(self, request: JobSearchRequest) -> JobSourceResult:
        leads = tuple(lead for lead in _LEADS if _matches(lead, request))
        return JobSourceResult(
            source_id=self.source_id,
            status=JobSourceStatus.SUCCESS,
            fetched_at=_CAPTURED_AT,
            leads=leads[: request.max_results],
        )


def _matches(lead: JobLead, request: JobSearchRequest) -> bool:
    if request.query is not None:
        searchable = " ".join(
            (
                lead.company,
                lead.title,
                lead.direction,
                *lead.locations,
                *lead.highlights,
            )
        ).casefold()
        if request.query.casefold() not in searchable:
            return False

    companies = {company.casefold() for company in request.companies}
    if companies and lead.company.casefold() not in companies:
        return False

    locations = {location.casefold() for location in request.locations}
    lead_locations = {location.casefold() for location in lead.locations}
    if locations and not locations & lead_locations:
        return False
    return not request.job_types or lead.job_type in request.job_types


def _lead(
    external_id: str,
    company: str,
    title: str,
    direction: str,
    source_url: str,
    highlights: tuple[str, ...],
    company_pool: CompanyPool = CompanyPool.ANCHOR,
    verification_status: JobVerificationStatus = JobVerificationStatus.NEEDS_REVERIFICATION,
    job_type: JobType = JobType.INTERNSHIP,
    locations: tuple[str, ...] = ("上海",),
) -> JobLead:
    return JobLead(
        lead_id=f"{_SOURCE_ID}:{external_id}",
        deduplication_key=f"{company.casefold()}:{title.casefold()}:上海",
        source_id=_SOURCE_ID,
        external_id=external_id,
        company=company,
        company_pool=company_pool,
        title=title,
        job_type=job_type,
        locations=locations,
        direction=direction,
        source_url=source_url,
        captured_at=_CAPTURED_AT,
        verification_status=verification_status,
        highlights=highlights,
    )


_LEADS = (
    _lead(
        "minimax-open-source-agent-ecosystem-intern",
        "MiniMax",
        "开源 Agent 开发者生态实习生",
        "Agent / LLM 应用",
        "https://vrfi1sk8a0.jobs.feishu.cn/379481/position/7674929052376942886/detail",
        ("Python", "Agent", "MCP", "每周 3 天以上"),
        CompanyPool.FOCUSED_AI,
        JobVerificationStatus.CLOSED,
    ),
    _lead(
        "minimax-agent-ai-infra-intern",
        "MiniMax",
        "Agent 研发实习生-AI Infra",
        "AI Infra",
        "https://vrfi1sk8a0.jobs.feishu.cn/379481/position/7685277183518427419/detail",
        ("Python", "Agent", "RAG/MCP", "每周 4 天以上"),
        CompanyPool.FOCUSED_AI,
        JobVerificationStatus.LIVE,
    ),
    _lead(
        "xiaohongshu-agent-development-intern",
        "小红书",
        "AI Agent 研发实习生",
        "Agent / LLM 应用",
        "https://job.xiaohongshu.com/campus/intern/position/21231",
        ("AI Agent", "在校生", "每周 4 天以上"),
    ),
    _lead(
        "xiaohongshu-foundation-model-agent-research",
        "小红书",
        "基础大模型 Agent 能力研究",
        "Agent 研究",
        "https://job.xiaohongshu.com/campus/intern/position/19823",
        ("大模型", "Agent", "不限年级"),
    ),
    _lead(
        "bytedance-payment-risk-algorithm-intern",
        "字节跳动",
        "国际支付风控算法实习生",
        "机器学习 / 风险建模",
        "https://jobs.bytedance.com/campus/position/7683144915764726069/detail",
        ("机器学习", "LLM", "图模型", "每周 4 天"),
        verification_status=JobVerificationStatus.LIVE,
    ),
    _lead(
        "apple-ml-engineer-intern-shanghai",
        "Apple",
        "Machine Learning Engineer Intern",
        "机器学习 / LLM",
        "https://jobs.apple.com/en-us/details/200609538-3715/machine-learning-engineer-intern-shanghai?team=STDNT",
        ("Python", "ML", "LLM", "全职 3-6 个月"),
        verification_status=JobVerificationStatus.LIVE,
    ),
    _lead(
        "nvidia-cuda-ai-test-intern",
        "NVIDIA",
        "CUDA Full Stack & AI Test Dev Intern",
        "AI Infra / 测试",
        "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/China-Shanghai/CUDA-Full-Stack---AI-Test-Dev-Intern---2027_JR2023666-1",
        ("LLM", "AI Agent", "测试评测", "至少 1 年"),
        verification_status=JobVerificationStatus.LIVE,
    ),
    _lead(
        "xiaohongshu-ai-community-product-trainee",
        "小红书",
        "AI x 社区产品培训生",
        "AI 产品",
        "https://job.xiaohongshu.com/campus/intern/position/20413",
        ("AI 产品", "社区", "2027 届及以后"),
        verification_status=JobVerificationStatus.LIVE,
    ),
    _lead(
        "apple-ai-tools-hardware-engineering",
        "Apple",
        "Software Engineering Intern - AI Tools for Hardware Engineering",
        "AI 工具 / 软件工程",
        "https://jobs.apple.com/en-us/details/200676912-3715/software-engineering-intern-ai-tools-for-hardware-engineering?team=STDNT",
        ("AI Tools", "TypeScript", "硕士在读", "全职至少 4 个月"),
        verification_status=JobVerificationStatus.LIVE,
    ),
    _lead(
        "minimax-foundation-model-evaluation-intern",
        "MiniMax",
        "大模型算法评测实习生",
        "模型评测",
        "https://vrfi1sk8a0.jobs.feishu.cn/379481/position/7655253685333936403/detail",
        ("大模型评测", "PyTorch", "每周 4 天以上", "至少 4 个月"),
        CompanyPool.FOCUSED_AI,
        JobVerificationStatus.LIVE,
    ),
    _lead(
        "bytedance-ai-search-intern",
        "字节跳动",
        "AI 搜索算法实习生-国际电商",
        "搜索 / 检索算法",
        "https://jobs.bytedance.com/campus/position/7615453398335588613/detail",
        ("机器学习", "大规模检索", "C++/Python", "2027 届"),
        verification_status=JobVerificationStatus.LIVE,
    ),
    _lead(
        "nvidia-cuda-test-development-intern",
        "NVIDIA",
        "Software Engineering Intern, CUDA Test Development - 2027",
        "CUDA / AI 测试",
        "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/China-Shanghai/Software-Engineering-Intern--CUDA-Test-Development---2027_JR2023645",
        ("C/C++", "Python", "AI Agent", "CUDA"),
        verification_status=JobVerificationStatus.LIVE,
    ),
    _lead(
        "unstructured-remote-software-engineer",
        "Unstructured",
        "Software Engineer - Public Sector",
        "Document AI / RAG",
        "https://jobs.ashbyhq.com/unstructured/8db76ba9-7c3a-451c-8e6d-c3447e6cbe75",
        ("Document AI", "Data Pipelines", "Remote", "Software Engineering"),
        company_pool=CompanyPool.FOCUSED_AI,
        verification_status=JobVerificationStatus.LIVE,
        job_type=JobType.FULL_TIME,
        locations=("远程",),
    ),
)
