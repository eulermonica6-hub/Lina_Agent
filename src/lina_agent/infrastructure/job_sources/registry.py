from lina_agent.domain.weekly_monitoring import MonitoredJobSource

MONITORED_JOB_SOURCES = (
    MonitoredJobSource(
        source_id="tencent-careers",
        company="腾讯",
        url="https://careers.tencent.com/",
        keywords=("Agent Memory", "RAG", "知识图谱", "评测", "向量检索"),
    ),
    MonitoredJobSource(
        source_id="bytedance-careers",
        company="字节跳动",
        url="https://joinbytedance.com/",
        keywords=("大模型应用", "搜索", "数据算法", "AI 产品"),
    ),
    MonitoredJobSource(
        source_id="alibaba-careers",
        company="阿里巴巴",
        url="https://talent.alibaba.com/",
        keywords=("搜索推荐", "智能客服", "AI 应用"),
    ),
    MonitoredJobSource(
        source_id="ant-group-careers",
        company="蚂蚁集团",
        url="https://talent.antgroup.com/",
        keywords=("大模型评测", "金融 AI", "Agent", "数据智能"),
    ),
    MonitoredJobSource(
        source_id="microsoft-careers",
        company="Microsoft",
        url="https://careers.microsoft.com/",
        keywords=("Applied Science", "Data Science", "AI Engineering"),
    ),
    MonitoredJobSource(
        source_id="amazon-shanghai",
        company="Amazon",
        url=("https://www.amazon.jobs/en/search?base_query=intern&loc_query=Shanghai%2C%20China"),
        keywords=("OpenSearch", "SDE", "AI/ML"),
    ),
    MonitoredJobSource(
        source_id="meltwater-careers",
        company="Meltwater",
        url="https://www.meltwater.com/en/careers",
        keywords=("AI", "Data", "Product Analytics"),
    ),
)
