from datetime import date
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["job discovery"])


class OpportunitySnapshot(BaseModel):
    opportunity_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    location: str = Field(min_length=1)
    direction: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    last_verified_at: date
    verification_status: Literal["needs_reverification"]
    highlights: tuple[str, ...]


class OpportunityFeed(BaseModel):
    data_as_of: date
    freshness: Literal["historical_snapshot"]
    source_note: str
    opportunities: tuple[OpportunitySnapshot, ...]


class AssistantMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class AssistantMessageResponse(BaseModel):
    answer: str
    mode: Literal["typed_preview"] = "typed_preview"
    suggested_action: Literal["view_opportunities", "upload_resume", "none"]


_OPPORTUNITIES = (
    OpportunitySnapshot(
        opportunity_id="minimax-open-source-agent-ecosystem-intern",
        company="MiniMax",
        title="开源 Agent 开发者生态实习生",
        location="上海",
        direction="Agent / LLM 应用",
        source_url="https://vrfi1sk8a0.jobs.feishu.cn/379481/position/7674929052376942886/detail",
        last_verified_at=date(2026, 9, 14),
        verification_status="needs_reverification",
        highlights=("Python", "Agent", "MCP", "每周 3 天以上"),
    ),
    OpportunitySnapshot(
        opportunity_id="minimax-agent-ai-infra-intern",
        company="MiniMax",
        title="Agent 研发实习生-AI Infra",
        location="上海",
        direction="AI Infra",
        source_url="https://vrfi1sk8a0.jobs.feishu.cn/379481/position/7685277183518427419/detail",
        last_verified_at=date(2026, 9, 14),
        verification_status="needs_reverification",
        highlights=("Python", "Agent", "RAG/MCP", "每周 4 天以上"),
    ),
    OpportunitySnapshot(
        opportunity_id="xiaohongshu-agent-development-intern",
        company="小红书",
        title="AI Agent 研发实习生",
        location="上海",
        direction="Agent / LLM 应用",
        source_url="https://job.xiaohongshu.com/campus/intern/position/21231",
        last_verified_at=date(2026, 9, 14),
        verification_status="needs_reverification",
        highlights=("AI Agent", "在校生", "每周 4 天以上"),
    ),
    OpportunitySnapshot(
        opportunity_id="xiaohongshu-foundation-model-agent-research",
        company="小红书",
        title="基础大模型 Agent 能力研究",
        location="上海",
        direction="Agent 研究",
        source_url="https://job.xiaohongshu.com/campus/intern/position/19823",
        last_verified_at=date(2026, 9, 14),
        verification_status="needs_reverification",
        highlights=("大模型", "Agent", "不限年级"),
    ),
    OpportunitySnapshot(
        opportunity_id="bytedance-payment-risk-algorithm-intern",
        company="字节跳动",
        title="国际支付风控算法实习生",
        location="上海",
        direction="机器学习 / 风险建模",
        source_url="https://jobs.bytedance.com/campus/position/7683144915764726069/detail",
        last_verified_at=date(2026, 9, 14),
        verification_status="needs_reverification",
        highlights=("机器学习", "LLM", "图模型", "每周 4 天"),
    ),
    OpportunitySnapshot(
        opportunity_id="apple-ml-engineer-intern-shanghai",
        company="Apple",
        title="Machine Learning Engineer Intern",
        location="上海",
        direction="机器学习 / LLM",
        source_url="https://jobs.apple.com/en-us/details/200609538-3715/machine-learning-engineer-intern-shanghai?team=STDNT",
        last_verified_at=date(2026, 9, 14),
        verification_status="needs_reverification",
        highlights=("Python", "ML", "LLM", "全职 3-6 个月"),
    ),
    OpportunitySnapshot(
        opportunity_id="nvidia-cuda-ai-test-intern",
        company="NVIDIA",
        title="CUDA Full Stack & AI Test Dev Intern",
        location="上海",
        direction="AI Infra / 测试",
        source_url="https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/China-Shanghai/CUDA-Full-Stack---AI-Test-Dev-Intern---2027_JR2023666-1",
        last_verified_at=date(2026, 9, 14),
        verification_status="needs_reverification",
        highlights=("LLM", "AI Agent", "测试评测", "至少 1 年"),
    ),
)


@router.get("/opportunities", response_model=OpportunityFeed)
async def list_opportunities() -> OpportunityFeed:
    return OpportunityFeed(
        data_as_of=date(2026, 9, 14),
        freshness="historical_snapshot",
        source_note="官方页面人工核验快照，不代表当前仍在招聘；申请前请打开官网重新确认。",
        opportunities=_OPPORTUNITIES,
    )


@router.post("/assistant/messages", response_model=AssistantMessageResponse)
async def create_assistant_message(
    request: AssistantMessageRequest,
) -> AssistantMessageResponse:
    normalized = request.message.casefold()
    if any(keyword in normalized for keyword in ("简历", "resume", "匹配")):
        return AssistantMessageResponse(
            answer=(
                "可以。打开“简历匹配”区域上传 TXT、Markdown 或 DOCX 简历，"
                "我会用当前岗位快照做证据化初筛。"
            ),
            suggested_action="upload_resume",
        )
    if any(keyword in normalized for keyword in ("岗位", "实习", "工作", "job", "agent")):
        return AssistantMessageResponse(
            answer="我已加载官方页面人工核验快照。它们不是实时岗位，请先打开官网确认仍在招聘，再上传简历进行匹配。",
            suggested_action="view_opportunities",
        )
    return AssistantMessageResponse(
        answer="当前对话是类型化预览，可帮你查看岗位快照或定位简历匹配入口；尚未联网自主搜索，也没有多轮记忆。",
        suggested_action="none",
    )
