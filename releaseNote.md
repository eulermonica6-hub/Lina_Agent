# Lina Release Notes

本文件记录 Lina 的可发布版本与重大变更。当前版本为 `0.2.39`，之后按可验收用户能力递增。

## Unreleased

- 产品目标调整为主动型个人求职 Agent：对话理解目标、官方岗位发现、持续监控与推送、调查和对比、职业支持，以及用户审批后的辅助投递。
- 0.2.25 现有文档摄取、证据、硬条件、匹配、gap、Reviewer、SQLite、Snapshot/Diff 和评测继续作为可信决策内核，不推倒重写。
- 近期唯一实现目标改为 `JobLead`、统一来源适配器和一个真实官方来源的手动搜索 API；Run 详情与恢复降为跨周期工作流的支撑能力。
- 明确自治等级：公开信息检索可自动执行，通知需渠道授权，外部提交需逐次预览和确认；绕过验证码、伪造经历与无人值守海投属于禁止能力。

## 0.2.39 - 2026-09-30

- 新增首个真实官方岗位列表解析器：通过 NVIDIA Workday CXS JSON 分页读取上海职位。
- 规范化职位编号、标题、地点、岗位类型、方向、发布时间、官方详情 URL 和 live 状态；支持关键词、公司、地点和岗位类型过滤。
- 开发/生产的手动搜索聚合核验快照与 NVIDIA 实时源；首页推荐继续只使用核验快照，避免公网失败影响首屏。
- 每周监控对 NVIDIA 使用真实解析器，其余公司继续使用入口健康探针；离线 Fixture 覆盖分页、结构变化、阻断、限流和网络失败。

## 0.2.38 - 2026-09-28

- 按市值与广义平台科技口径审核国内外科技公司 Top 10，并记录排名、日期与来源。
- 国内新增拼多多、网易、小米、美团、快手、中芯国际、京东和百度；国外新增 Alphabet / Google、TSMC、Meta、SpaceX、Broadcom 和 Tesla。
- 公司目录由 32 家扩展为 46 家；字节跳动、蚂蚁集团、小红书和 Meltwater 因岗位相关性继续保留，但不伪装成对应市值 Top 10 成员。

## 0.2.37 - 2026-09-28

- 将 32 家公司从 Python 硬编码迁移到可人工审核的 `company_catalog.toml` 单一数据源。
- 清单完整记录公司分组、官方招聘入口、关注关键词、地区和纳入理由，并随安装包发布。
- 运行时通过 Pydantic 校验清单结构，同时拒绝重复公司名和重复来源 ID。

## 0.2.36 - 2026-09-28

- 首页推荐从 9 条缩减为 6 条，与两列岗位卡组成稳定的三行布局。
- 内部公司池细分为国内大厂、国外大厂和探索型；默认 6 条各取 2 条，某类不足时由其余高分 live 岗位补位。
- 推荐同分项由每周轮换改为按当天日期每日轮换；每周来源健康监控频率保持不变。

## 0.2.35 - 2026-09-28

- 右侧对话栏新增 3 条常用提示词，点击即可发送并开始对话。
- 侧栏展开时岗位改为留白更充足的两列卡片，桌面筛选默认折叠，减少首页同时出现的控件。
- 岗位卡展示公司 logo；官方图标不可用时使用公司首字回退，不影响岗位浏览。

## 0.2.34 - 2026-09-28

- Lina 对话改为类似 VS Code Copilot 的右侧全高停靠栏，首次访问默认展开，主页面自动让出空间。
- 对话栏支持拖动左侧分隔线或使用方向键调节宽度，可主动收起；开关状态和宽度保存在本地浏览器。
- 移动端使用全宽抽屉，不压缩岗位页面；决策工具继续显示原有运行状态，不展示对话栏。

## 0.2.33 - 2026-09-28

- 首页删除英文 eyebrow、大型 DISCOVER 水印和重复“查看岗位”CTA，压缩标题、Feed 和筛选间距，使首张岗位卡进入常见桌面与移动首屏。
- 筛选器桌面保持单行，移动端默认折叠、展开后采用两列；默认上海和实习/校招不变。
- 对话入口从单字母圆钮升级为 `L` 标记加“和 Lina 对话”文案；桌面固定悬浮，移动端进入首屏文档流，不遮挡岗位卡。
- 根路径统一称“机会首页”，旧结构化功能明确位于 `/workbench`；Coding Plan 区分类型化对话预览和未实现的实时工具/多轮记忆。
- 234 项测试通过，其中 24 项 Playwright；核心语句和分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.32 - 2026-09-28

- 全面审计首页、推荐、简历、对话、监控和活跃文档，确认“可信匹配内核”与目标求职 Agent 的剩余差距。
- 公司池、配额和去重键改为内部实现：移除公共公司/监控目录 API、公司雷达和岗位池徽标。
- 重新核验官方详情页：主页仅推荐 9 条 live 岗位；明确下线和无法确认的岗位仍可搜索，但不能进入首页。
- 产品文档统一以“首页 9 条真实有效推荐、完整筛选、简历匹配、对话工具化”为目标；对话实时查询、简历优化与职业规划仍明确为待实现。
- 233 项测试通过，其中 23 项 Playwright；核心语句和分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.31 - 2026-09-28

- 探索池新增 Garena，总公司目录达到 32 家：10 家平台型主池与 22 家专注型 AI 探索池；TapTap/心动因缺少可解析官方招聘页暂列待补证。
- `JobLead` 新增 internship、campus、full_time、unknown 岗位类型；首页推荐优先上海/明确远程和实习/校招。
- 搜索表单默认上海与实习/校招，用户仍可修改关键词、公司、地点和岗位类型检索完整当前数据集。
- 主页移除结构化决策台，旧画像、单 JD 硬条件和历史审计迁移到 `/workbench`，并保留导航入口。
- 新增公司与岗位准入标准，明确公司级关注不能覆盖岗位级资格、方向、成长价值和风险判断。
- 233 项测试通过，其中 23 项 Playwright；核心语句和分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.30 - 2026-09-28

- 公司宇宙扩展到 31 家：10 家平台型主池与 21 家专注型 AI 探索池；新增 Sierra、Scale AI、Lambda、Cartesia、Harvey、Vapi、WRITER、Unstructured、Glean 和 Arize AI。
- 首页固定 3×3 推荐：前 6 个主池、后 3 个探索池；偏好公司、近期点击和搜索方向影响池内排序，同分项按周次轮换。
- 新增 `POST /opportunities/recommended`；浏览器偏好保存在本地，不上传简历内容或建立服务端隐式画像。
- 每周监控统一扩展到 31 个入口；31 源首次运行中 30 个入口可访问但解析器待实现，小红书本次为 network_error。
- 正式公司成员资格按月人工复核，来源健康按周自动更新；Replicate、失效的 Mistral URL、需登录的 Hugging Face Jobs 和无职位入口的 Groq 未纳入正式目录。
- 227 项测试通过，其中 23 项 Playwright；核心语句和分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.29 - 2026-09-28

- 建立 21 家公司双池目录：10 家平台型主池与 11 家专注型 AI 探索池，每家公司记录官方 Careers、地区、方向标签和关注理由。
- 探索池包含 MiniMax、Baseten、Cohere、Fireworks AI、Anyscale、LlamaIndex、Pinecone、Weaviate、ElevenLabs、LangChain 和 Together AI。
- `JobLead` 新增公司池，发现服务按 anchor/focused_ai 交替混排，避免大厂岗位数量淹没探索机会。
- 新增 `GET /companies?pool=` 与网页公司雷达；每周监控统一扩展到 21 个入口，不维护第二份名单。
- 21 源真实探针中 20 个入口可访问但解析器待实现，小红书本次为 network_error；失败未中断周报或伪装成零岗位。
- 226 项测试通过，其中 22 项 Playwright；核心语句和分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.28 - 2026-09-28

- Lina 新增每周监控运行模型，使用 `lina-weekly:YYYY-MM-DD` 周一幂等 ID，并区分 complete、partial 和 failed。
- 注册腾讯、字节、阿里、蚂蚁、Microsoft、Amazon 上海和 Meltwater 7 个官方入口及关注关键词。
- 新增 HTTP 健康探针，分类成功正文、空页、阻断、限流、服务错误和网络异常；HTTP 200 但无解析器时明确为 `partial/listing_parser_pending`。
- 新增 `lina-monitor` CLI 和每周一 01:00 UTC 的 GitHub Actions schedule，报告以 JSON artifact 保存且不读取私人简历或账号秘密。
- 首次真实运行 7/7 入口可读取正文，但 7/7 岗位列表解析器待实现；没有伪报实时岗位或零岗位。
- 222 项测试通过，其中 21 项 Playwright；核心语句和分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.27 - 2026-09-28

- 新增 `JobLead`、`JobSearchRequest`、`JobSourceResult` 和来源健康状态，分离来源内 ID 与跨来源去重键。
- 新增 `JobSourceAdapter` 与 `JobDiscoveryService`，聚合来源、保留失败状态、跨来源去重并在去重后应用全局 limit。
- 将 7 条历史岗位迁移到 `VerifiedSnapshotJobSource`，API 路由不再持有岗位数据。
- 新增 `POST /opportunities/search`，支持关键词、公司和地点过滤；首页加入对应搜索表单和来源健康展示。
- 210 项测试通过，其中 21 项 Playwright；语句和分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.26 - 2026-09-28

- 首页新增 7 条 AI/Agent 岗位 Feed，全部来自 2026-09-14 官方页面人工核验记录，并明确标记历史快照和待官网复核。
- 用户默认只需上传简历，前端会把当前 Feed 转为 Markdown 岗位目录调用现有文件 Agent；仍可切换到自带完整 JD 目录。
- 右下角新增 Lina 对话按钮和响应式对话面板；类型化预览可识别岗位与简历意图并导航到对应区域。
- 新增 `GET /opportunities` 与 `POST /assistant/messages`，当前不访问公网、不调用 LLM，也不保存会话。
- 203 项测试通过，其中 20 项 Playwright 浏览器测试；桌面/移动端无横向溢出，Ruff 与 Pyright strict 通过。

## 0.2.25 - 2026-09-28

- 工作台新增文件 Agent：浏览器可上传 TXT/Markdown/DOCX 简历与 Markdown JD 目录，调用现有 `POST /agent/runs`。
- 自动决策信号与 LLM 保持显式 opt-in；仅开启自动信号时提交到岗、时长和六类方向确认，保留有效的 `0.0` 偏好。
- 运行完成后展示 Top 匹配、聚合 gap 和 warning，并复用历史加载函数自动刷新脱敏 Snapshot。
- 独立 revision 防止文件或参数变化后旧响应污染界面；API 失败恢复按钮并展示服务端 detail。
- 文件内容只发送到本地 API，历史不展示或保存 Base64、正文、offset 与私密文件名。
- 198 项测试通过，其中 17 项 Playwright 浏览器测试；桌面/移动端无横向溢出，Ruff 与 Pyright strict 通过。

## 0.2.24 - 2026-09-28

- 工作台新增只读 Run 历史面板，手动刷新最近 20 条 Snapshot，并默认比较次新与最新 Run。
- 结构化展示输入/确认/计划变化、排名位移、分数 delta、岗位集合变化和 gap 新增/解决。
- 历史与 Diff 请求使用独立 revision 防止过期响应，空状态和失败后按钮恢复均有浏览器测试。
- 桌面三列、移动单列布局通过视觉验收，sticky topbar 不再遮挡滚动目标；前端不请求或展示原文。
- 下一步将文件 Agent 运行入口接入工作台，运行后自动刷新历史。
- 193 项测试通过，语句/分支覆盖率 100%，其中 12 项 Playwright 浏览器测试通过；Ruff 与 Pyright strict 通过。

## 0.2.23 - 2026-09-24

- 新增 `AgentRunDiff` 与 GET diff API，不加载原始正文即可比较两个历史 Run。
- 比较文档 content hash、确认 facts hash、状态/计划、排名位置、分数组件和 gap 新增/解决。
- 同 catalog number 但 title/company 不同的岗位标记为 replacement，不计算伪 score delta。
- 兼容 v1 Snapshot fallback；position delta 负数表示上升、正数表示下降。
- 下一步在工作台增加只读 Run 历史与 Diff 视图。
- 189 项测试通过，语句/分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.22 - 2026-09-24

- 新增 metadata-only `DocumentReference`，分离内容 document ID 与 resume/JD 角色 reference ID，不保存正文或文件名。
- 新增 `CandidateConfirmationVersion`：随机版本 ID 表示确认事件，稳定 facts hash 表示事实内容。
- Snapshot 默认升级到 schema v2，关联两个文档引用和可选确认版本，同时兼容读取 v1。
- 新增文档引用与确认版本 GET API；SQLite schema 升级到 v3，文档引用 insert-if-absent 保持不可变。
- 下一步实现不加载原始正文的 Snapshot diff。
- 185 项测试通过，语句/分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.21 - 2026-09-24

- 新增 `AgentRunSnapshot(schema_version=1)`，保存文档引用、请求确认、匹配/gap 摘要、步骤状态、计划与 Review。
- Snapshot 明确排除 Base64 输入、原文 evidence、offset、源文件名、step summary 和 warning 原文。
- POST `/agent/runs` 成功后持久化 Snapshot；新增单条与最近列表 GET API，支持跨 FastAPI app 重启查询。
- SQLite schema 从 v1 统一迁移到 v2；recent 按 UTC `created_at` 排序，不依赖 rowid。
- 下一步定义文档引用和候选确认版本；历史可查询不等于执行可恢复。
- 179 项测试通过，语句/分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.20 - 2026-09-24

- 新增 SQLite Repository adapter，结构化 Web 候选人画像和岗位可跨进程重启恢复。
- development/production 默认使用 `data/lina.db`；test 或 `database_path=None` 保持内存隔离，路径可用 `LINA_DATABASE_PATH` 覆盖。
- 使用 Pydantic JSON、UUID upsert、WAL、busy timeout、独立连接和 `asyncio.to_thread`；10 条并发写入验收通过。
- 两个独立 repository 与两个独立 FastAPI app 的重启测试通过；Agent Run、证据、确认和计划仍未持久化。
- CUDA GPU 验收延期为外部任务，不阻塞 Lina 持久化主线；下一步定义版本化 `AgentRunSnapshot`。
- 174 项测试通过，语句/分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.19 - 2026-09-24

- 新增 CUDA runner preflight，检查 Linux/x64、磁盘、Git/C++/Ninja、CUDA PyTorch、GPU、NVCC 与 nvidia-smi。
- self-hosted workflow 在编译前使用 `--require-ready` fail-fast，并保留结构化阻塞原因。
- 新增安全注册、labels、触发、artifact 验收和清理手册；临时 runner token 不进入仓库、聊天或报告。
- 当前 Mac 探针按事实返回 `ready=false`；模拟 NVIDIA Linux runner 的 ready 路径测试通过。
- 下一步仅剩外部操作：注册 NVIDIA runner 并触发 `CUDA Benchmark`，通过 artifact 后才能回写技能证据。
- 本地推理/C++/CUDA 契约组合测试 16 项通过，6 项 GPU 测试因环境缺失明确跳过。
- 核心 167 项测试通过，语句/分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.18 - 2026-09-24

- 新增 CUDA RMSNorm kernel、PyTorch CUDA 注册、JIT loader、环境探针、条件测试和同步 benchmark。
- 新增 self-hosted NVIDIA workflow，固定 GPU 型号/能力、误差、延迟、吞吐和显存报告契约。
- 本机无 CUDA build、NVCC 和 NVIDIA runtime：本地 14 项实验通过、6 项 GPU 测试带原因跳过，不声明 CUDA 性能完成。
- 修复 inference benchmark workflow 的测试步骤缩进，并用三实验组合测试验证模块收集。
- 下一步是在真实 NVIDIA runner 执行 GPU artifact；通过后才回写技能证据并复跑排序。
- 核心 167 项测试通过，语句/分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.17 - 2026-09-24

- 新增 PyTorch C++ RMSNorm custom op、ATen 注册、JIT/Ninja 构建、输入校验和数值测试。
- 固定 `512 x 1024` 输入上，C++ median `0.136ms`，相对 Python/ATen reference 加速 `1.60x`，最大误差 `1.91e-6`。
- 记录首轮 C++ 仅 `0.38x` 的负结果，并通过 float 累加、快速数学与并行粒度优化修复。
- 推理手动 CI 同进程运行 12 项实验测试，并上传 CPU decoder 与 C++ RMSNorm 两份报告。
- 下一阶段为 CUDA Kernel；之后依次进入证据回写与重排、持久化和产品工作流。
- 核心 167 项与推理/C++ 专项 12 项测试通过；核心语句/分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.16 - 2026-09-24

- 新增独立 PyTorch causal decoder 推理实验，固定模型、输入、warmup、同步和 JSON 报告契约。
- 新增 `inference` optional extra、专用测试、VS Code 任务和手动 CPU benchmark workflow，不污染默认安装与主 CI。
- Apple Silicon 实测 MPS median `5.42ms`、`94.5k tokens/s`，相对 CPU 加速 `3.28x`，最大绝对误差 `1.19e-6`。
- 该结果是合成小模型技能证据，不宣称生产 LLM serving；下一步实现 C++ PyTorch 扩展。
- 核心 167 项与推理专项 4 项测试通过；核心语句/分支覆盖率 100%，Ruff 与 Pyright strict 通过。

## 0.2.15 - 2026-09-24

- 新增确定性技能证据计划，从目标岗位 required 缺口生成带产出物、验收标准和时间预算的行动。
- 评测 CLI 新增 `--evidence-plan-for`，可从冻结 Gold 重建目标岗位并输出计划 JSON。
- CUDA 进入技能 taxonomy；NVIDIA 岗生成 PyTorch、C++、CUDA 共 60 小时的证据计划，并通过现有 Reviewer。
- 两个技能 Gold 的 Precision、Recall、Exact Match 和引用支持率均保持 `1.0`；唯一排序逆序不通过调权重消除。
- 167 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.14 - 2026-09-24

- 新增 4 条国内与 1 条外企完整官方 JD，扩展 Gold 为 6 岗，suite 为 2 集 11 岗。
- 修复多城市首项误判、“不少于”范围遗漏和优先时长误作硬条件。
- 新增 AI 产品方向；区分 TensorRT/GPU 推理基础设施与 CUDA 测试场景。
- 任一明确硬条件失败时执行排序 veto；仅北京岗位造成的 4 个逆序消失，unknown 语义不变。
- 扩展集 hard/direction/证据指标均为 `1.0/0.0` 或 `1.0`；Pairwise `0.933`，保留 1 个可由技能缺口解释的逆序。
- 163 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.13 - 2026-09-24

- 从完整官方 JD 建立第二个独立私有 Gold，suite 扩展为 2 个数据集、6 个岗位。
- suite 新增 macro/minimum direction coverage，避免 MAE 跳过 unknown 后掩盖整集召回失败。
- 真实新集暴露“测试自动化 / test automation”方向别名缺口；修复后两集方向覆盖率、direction MAE 均为 `1.0 / 0.0`。
- 单岗位集只验证抽取与证据契约，不宣称跨岗位排序能力；自动综合排序继续显式 opt-in。
- 157 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.12 - 2026-09-24

- 新增版本化多 Gold manifest 与 `--auto-signal-suite` 评测入口。
- 汇总数据集数、岗位数、JD 实际方向族覆盖、direction MAE 宏平均/最大值，以及 Top-1/Pairwise 宏平均和最差 Pairwise。
- 私有 suite 首轮仍为 1 个冻结集、5 个岗位；五类方向覆盖率 `1.0`，macro direction MAE `0.0`，macro/minimum Pairwise `1.0/1.0`。
- 建立 5 项私有扩展标注 backlog；缺完整 JD 或用户排序的候选不会提前进入 Gold。
- 156 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.11 - 2026-09-24

- 将五类候选人方向偏好贯通 `CareerMatchAgent` 的路径与文档入口、HTTP API 和本地 CLI。
- API 新增 `candidate_direction_preferences`；CLI 新增五个 `--direction-*` 参数，分数范围均为 `0..1`。
- 未开启自动决策信号时拒绝方向偏好输入，确认来源继续独立记录为 `user_confirmation`。
- 自动综合排序继续显式 opt-in；下一步扩充冻结 Gold，验证跨岗位族稳定性。
- 153 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.10 - 2026-09-21

- 新增五类 `0-1` 候选人方向偏好确认及独立 `user_confirmation` 来源，不伪造文档证据。
- 将 AI 平台/Infra 与 CUDA 全栈/AI 测试拆为独立方向，岗位多方向分使用确定性均值。
- 私有 Gold 可透传方向确认；确认后 direction MAE `0.0`、Pairwise/Top-1 `1.0/1.0`、逆序对 `0`。
- 本版本只完成领域契约与私有评测，Agent/API/CLI 接线是下一步；自动综合排序继续显式 opt-in。
- 145 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.9 - 2026-09-15

- Gold 排名支持类型化并列组；Pairwise 和逆序对跳过组内顺序，Top-1 接受并列首组任一岗位。
- 自动信号报告新增逐岗技能、hard、自动/人工方向、总分分解和结构化逆序对。
- 用户确认岗位 3/4 同优先级后，人工 oracle Pairwise 恢复 `1.0`；自动 Pairwise 按 9 个明确顺序对重算为 `0.778`。
- 剩余两个逆序对定位为方向偏好强度缺失；自动综合排序继续保持显式 opt-in，不调整默认权重。
- 143 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.8 - 2026-09-15

- 自动决策信号评测可从私有 Gold 读取类型化候选人投入确认。
- 使用每周 5 天、连续 12 个月的真实确认复跑 18 项硬条件：逐项已知率 `1.0`、unknown `0`、hard MAE `0.0`。
- 状态准确率和证据 Precision/Recall/有效率均保持 `1.0`，人工确认仍不计作文档证据。
- 自动排序 Top-1 保持 `1.0`，Pairwise 保持 `0.7`；默认排序不变，下一步分析方向标签与逆序对。
- 137 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.7 - 2026-09-14

- Agent 的路径和文档入口可向自动决策信号透传候选人投入确认。
- API 新增 `candidate_availability`，误在 skill-only 模式使用时返回 422。
- CLI 新增 `--candidate-weekly-days` 和 `--candidate-duration-months`，并在未开启自动决策信号时拒绝执行。
- 确认值继续以 `user_confirmation` 独立记录，不生成伪造的简历原文 offset；默认排序行为不变。
- 下一步使用真实确认值复跑逐项 Gold，再评估是否满足默认启用门槛。
- 136 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.6 - 2026-09-14

- 新增候选人每周可到岗天数和连续实习月数的类型化确认模型。
- 确认事实独立记录值、单位和 `user_confirmation` 来源，不伪造简历原文 offset。
- 自动硬条件抽取可选消费确认值；未提供时继续保持 `unknown`。
- 本版本只完成领域契约，Agent/API/CLI 接线是下一步，默认排序行为不变。
- 129 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.5 - 2026-09-14

- 支持毕业年份/届次下界、基本信息行首城市、月份范围和年/月换算。
- 私有 Gold 新增 18 个唯一硬条件逐项标签，覆盖状态与双侧最小证据。
- 自动评测新增逐项已知率、状态准确率、证据 Precision/Recall 与 offset 有效率。
- 5 JD 上逐项状态和证据指标均为 `1.0`，已知率为 `0.5`，Pairwise 保持 `0.7`。
- 新增决策信号行为准则；明确 unknown、最小证据、Gold 冻结和默认启用门槛。
- 自动综合排序继续保持显式 opt-in；下一步是候选人投入事实确认，不调整权重。
- 128 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.4 - 2026-09-14

- 新增毕业届次、学历、地点、每周到岗天数和持续月份的证据化自动抽取。
- 硬条件逐项返回 `met`、`unmet` 或 `unknown`；未知项不进入兼容度分母并产生人工确认警告。
- 新增四类方向标签；仅在候选人存在明确方向证据时判定匹配或不匹配。
- 文件 Agent、CLI 和 API 可显式启用自动综合排序，默认仍保持 skill-only。
- 新增独立 `--auto-signals` 评测；5 JD 上硬条件覆盖率 `0.6`、Pairwise `0.7`、Top-1 `1.0`。
- 自动结果仍低于人工 oracle，且只有 5 个岗位；当前不默认启用。
- 121 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.3 - 2026-09-14

- 新增硬条件兼容度与方向适配度决策信号，并保留技能原始分和人工解释。
- 文件 Agent 可选消费已确认信号；未提供时继续保持 skill-only 行为。
- 新增 skill-only、hard+skill、hard+direction+skill 三组消融评测。
- 私有 5 JD Gold 上，前两组 Pairwise 均为 `0.3`；人工确认全信号达到 oracle Pairwise/Top-1 `1.0/1.0`。
- 该结果不代表自动抽取能力；CLI/API 尚未自动生成或默认启用综合排序。
- 116 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.2 - 2026-09-14

- 保存 5 条优先上海 AI 实习的私有官方正文快照、匿名 JD 目录和人工技能/Top-K Gold Label。
- 新增技能分类、候选人匹配、引用有效率、引用支持率、Top-1 与 Pairwise Accuracy 评测。
- 将技能覆盖权重提取为类型化配置，并搜索 20 组可解释权重；最佳组合仍无法命中 Gold Top-1，因此不修改默认权重。
- 补齐 `LLMs` 与 `HTTP / API` 等官方正文别名；首轮冻结数据上的技能、匹配和引用指标均达到 1.0。
- 0.2.1 发布时“尚未形成技能与 Top-K Gold”的限制已解除；当前剩余限制是排序尚未接入硬条件和方向适配特征。
- 111 项自动化测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 0.2.1 - 2026-09-14

- 新增可提交的 VS Code 工作区，固化推荐扩展、FastAPI/匿名 Agent/pytest 调试入口，以及依赖、测试和完整质量门禁任务。
- 新增完整工程代码技术书，统一代码框架、领域契约、双链数据流、扩展方法和从 Gold Set 到语义匹配的未来行动顺序。
- 移除 Pyright 对 `.venv` 的单一路径硬编码，使 Windows `.venv-windows` 与 WSL `.venv-wsl` 可由各自的 `uv run`/编辑器解释器解析。
- 新增当前 Agent 工程架构与数据流基线，明确 Web 硬条件链和文件证据链尚未统一。
- 新增官方公开 JD 离线摄取与匿名化脚本，建立 10 条正式岗负例候选。
- 完成国内外 30 余家公司官网核验，选出 5 条上海 AI 实习优先候选，并保留未声明和官网受阻状态。
- 为证据与文档区块增加严格递增的字符偏移校验，拒绝倒置或空区间。
- 为摄取、匿名化、固定职位消失和偏移不变量增加离线回归测试；文档契约覆盖迭代 017-019。

### 使用边界

- 官网核验与摄取是人工触发的数据准备流程，不是产品内联网搜索或持续岗位监控。
- 5 条优先候选尚未全部保存完整正文，也尚未形成技能与 Top-K Gold Label。

## 0.2.0 - 2026-08-27

把单一顺序脚本升级为可验证、可降级的多节点职业分析 Agent 内核；前端工作台暂不扩展。

完整验收命令和预期结果见 [0.2.0 发布测试手册](docs/RELEASE_TESTING_0.2.0.md)。

### 核心能力

- Supervisor 显式编排文档摄取、候选人分析、岗位分析、证据匹配、缺口聚合、行动计划和计划复核角色。
- 新增跨 Top-K 岗位的能力缺口聚合，区分硬性与优先技能缺口，计算影响岗位和确定性优先级，并汇总已有证据优势。
- 智能行动计划必须给出目标技能、具体行动、原因、产出物、验收标准和时间预算。
- 新增确定性计划复核；模型引用候选人和 JD 中都不存在的技能、优先级不连续或任务重复时，拒绝计划进入正式结果。
- `POST /agent/runs` 新增显式 `use_llm`，CLI 与 API 使用同一条计划和复核链路。

### 可靠性

- Provider 配置缺失、网络失败、限流、服务错误、坏 JSON 或 Schema 不合格时，Agent 返回 `degraded`，保留确定性 Top-K 和缺口分析。
- Trace 为每一步记录专业角色以及 `complete`、`failed` 或 `skipped` 状态。
- 默认仍不调用模型；只有 CLI `--use-llm` 或 API `use_llm=true` 才会发送最小化结构数据。
- Groq Qwen 3.6 使用官方 `reasoning_effort=none` 和 JSON mode，防止长 `<think>` 占满输出预算；解析器也能跳过前置推理文本中的无关 JSON。
- 匿名公开 Fixture 的真实链路返回 `complete`，Groq 生成 3 项行动并通过 Reviewer，共使用 896 Token。

### 使用边界

- 当前是一个 Supervisor 加可独立测试的专业节点，不是多个自主 Agent 自由对话。
- 仍无持久化、断点恢复、自然语言会话、PDF/OCR、联网岗位采集或自动投递。
- Web 首页继续使用原有确定性工作台，本版本不提前包装新的前端展示。

## 0.1.2 - 2026-08-27

扩展经济型模型路由和凭据级故障切换。

完整验收命令和预期结果见 [0.1.2 发布测试手册](docs/RELEASE_TESTING_0.1.2.md)。

### 新增

- 接入 OpenAI-compatible Agnes Provider，默认模型为 `agnes-2.5-flash`。
- 同一密钥文件可保存多个用户有权使用的 Groq 账号 key；只在前一个调用失败时按文件顺序尝试，不并发调用。
- 免费优先自动路由升级为多个 Groq 配置、Agnes、NVIDIA，再按显式设置选择付费 DeepSeek。
- 本机私有 `.env` 已按用户授权允许 DeepSeek 作为最终付费回退；仓库默认仍保持关闭。

### 可靠性与验证

- 单个凭据遇到 401/403、429、网络错误、无效响应或选定 5xx 时可切换下一配置；400 等请求错误立即失败。
- 真实密钥文件安全解析为 10 个 Groq、1 个 Agnes、1 个 NVIDIA 和 1 个 DeepSeek 配置，过程不输出 key。
- Agnes `agnes-2.5-flash` 与 DeepSeek `deepseek-v4-flash` 均使用无隐私最小提示完成真实连通性验证。
- 修复本机 Git/libcurl 到 GitHub 443 超时：使用只允许 `github.com:443` 的临时 Python CONNECT 转发完成同步，结束后删除代理，不修改全局 Git 配置。

### 使用边界

- 多 key 只应用于用户有权使用的独立账号故障切换；同一 organization 的多个 key 不会增加组织级限额。
- DeepSeek 是付费 Provider，仓库级默认配置不自动启用。

## 0.1.1 - 2026-08-26

从确定性工作台升级为可本地使用的有界职业匹配 Agent。

### 新增

- 读取 UTF-8 TXT、Markdown 与 DOCX，并为规范化文本块生成稳定文档 ID、SHA-256 指纹和字符偏移。
- DOCX 直接解析 OOXML 正文、表格和文本框；没有可读文本时显式失败。
- 将结构化 Markdown JD 目录解析为独立岗位、职责、要求、来源和上下线状态。
- 从简历与 JD 提取规范化技能证据，区分明确要求、优先项与职责上下文，输出可解释 Top-K 覆盖排序。
- 使用单 Supervisor 编排摄取、事实抽取、目录解析、排序和可选智能计划，并返回逐步 Trace。
- 新增 `lina-match` / `python -m lina_agent.cli` 本地入口和 `POST /agent/runs` Base64 文件 API。
- 新增 Groq、NVIDIA、DeepSeek 的 OpenAI-compatible Provider；默认免费优先路由为 Groq 到 NVIDIA，DeepSeek 仅显式选择或允许付费回退时启用。
- 新增 `--use-llm` 智能行动计划；只向模型发送技能标签和岗位匹配摘要，不发送文件名、联系方式或简历原句。

### 可靠性

- 修复 Windows 默认文本编码下读取 UTF-8 JSON Fixture 的失败。
- 新增 Linux/Windows CI 矩阵，并强制从 `uv.lock` 安装依赖。
- 新增 8 个正式 Playwright 竞态测试，覆盖候选人保存、岗位保存、抽取和匹配的过期成功与失败响应。
- Provider 错误不回显响应正文或密钥；429、网络错误、无效响应和选定 5xx 可跨服务降级。
- 浏览器测试失败时保留 Playwright Trace，便于复现前端状态问题。

### 验证

- 7 份私有 DOCX 均在本地完成解析，每份得到 42–104 个证据块。
- 真实 JD 文件稳定解析出 29 个岗位，默认排除 1 个不可投递岗位。
- 免费 Groq `qwen/qwen3.6-27b` 使用无隐私探针完成真实连通性验证。
- 私有简历的模型调用未执行；没有得到敏感派生数据外传的明确授权。

### 已知限制

- DOCX 不读取页眉页脚、批注、图片内文字或扫描件 OCR；尚不支持 PDF。
- 当前技能词表和权重尚未用人工 Top-K 标注集校准，覆盖分不是录取概率。
- 智能计划是显式 opt-in；当前 API Agent 路径仍为确定性运行。
- 尚无数据库、断点恢复、会话记忆、岗位采集和多智能体协作。

## 发布规则

每次重大更新推送前必须完成：

1. 在 `src/lina_agent/__init__.py` 更新运行时版本。
2. 在 `pyproject.toml` 同步项目版本。
3. 在本文件顶部新增对应版本记录，写明新增能力、重要修复、验证结果和已知限制。
4. 确认页面左上角显示的新版本；页面版本由运行时 `__version__` 自动渲染，无需修改 HTML。
5. 按 [文档治理清单](docs/DOCUMENTATION_GOVERNANCE.md) 统一 Review 并更新所有重要文档。
6. 运行 Ruff、Pyright、pytest 和必要的真实浏览器验收。
7. 完成提交并推送，确保发布记录、重要文档与代码位于同一个 commit。

版本一致性由 `tests/test_versioning.py` 自动检查；任一版本来源未同步时，测试必须失败。

## 0.1.0 - 2026-08-24

首个可演示的确定性职业决策工作台版本。

### 新增

- 候选人画像与岗位领域模型。
- 候选人、岗位和匹配 API。
- 中文岗位硬条件抽取，覆盖毕业年份、学历、经验和地点。
- 带原文与字符偏移的抽取证据预览。
- 确定性硬条件匹配，一次返回全部失败原因。
- Repository 协议与内存适配器。
- 浏览器工作台、匿名示例和连续分析状态管理。
- 6 个合成、人工标注的解析器评测案例。
- 面向 Agent 工程评审的中文 README 与产品截图。
- 页面左上角版本标识。

### 可靠性

- 38 个自动化测试通过，语句和分支覆盖率均为 100%。
- pre-commit 执行 Ruff；CI 执行 Ruff、Pyright strict 和带 100% 覆盖率门槛的 pytest。
- 解析器基线：`10 TP / 0 FP / 6 FN`，Precision 1.0、Recall 0.625、Exact Match 0.5。
- 修复偏好条件误判、地点切割、空评测集满分和浏览器异步旧响应覆盖新状态等问题。

### 已知限制

- 当前版本尚未接入 LLM、多轮对话或自主规划。
- 抽取证据尚未随已确认岗位和匹配报告持久化。
- 数据使用进程内存储，服务重启后清空。
- 浏览器延迟响应场景已手工验证，尚未加入正式 Playwright 自动化测试。
- 尚未实现简历文件解析、语义匹配、在线岗位采集与公司调研。
