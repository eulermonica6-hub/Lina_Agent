const state = {
    candidateId: null,
    jobId: null,
    revision: 0,
    extractionApplied: false,
    historyRevision: 0,
    diffRevision: 0,
    agentRevision: 0,
    historyRuns: [],
    opportunities: [],
};

const elements = {
    profileForm: document.querySelector("#profile-form"),
    jobForm: document.querySelector("#job-form"),
    runMatch: document.querySelector("#run-match"),
    runState: document.querySelector("#run-state"),
    resultPanel: document.querySelector("#result-panel"),
    resultTitle: document.querySelector("#result-title"),
    resultSummary: document.querySelector("#result-summary"),
    reasonList: document.querySelector("#reason-list"),
    extractConstraints: document.querySelector("#extract-constraints"),
    evidencePanel: document.querySelector("#evidence-panel"),
    evidenceList: document.querySelector("#evidence-list"),
    extractionWarning: document.querySelector("#extraction-warning"),
    resetWorkbench: document.querySelector("#reset-workbench"),
    refreshHistory: document.querySelector("#refresh-history"),
    historyCount: document.querySelector("#history-count"),
    historyEmpty: document.querySelector("#history-empty"),
    historyContent: document.querySelector("#history-content"),
    historyList: document.querySelector("#history-list"),
    baseRun: document.querySelector("#base-run"),
    targetRun: document.querySelector("#target-run"),
    compareRuns: document.querySelector("#compare-runs"),
    diffPanel: document.querySelector("#diff-panel"),
    diffFacts: document.querySelector("#diff-facts"),
    rankingChanges: document.querySelector("#ranking-changes"),
    scoreChanges: document.querySelector("#score-changes"),
    gapChanges: document.querySelector("#gap-changes"),
    fileAgentForm: document.querySelector("#file-agent-form"),
    agentAutoSignals: document.querySelector("#agent-auto-signals"),
    agentConfirmations: document.querySelector("#agent-confirmations"),
    agentRunStatus: document.querySelector("#agent-run-status"),
    agentResult: document.querySelector("#agent-result"),
    agentResultTitle: document.querySelector("#agent-result-title"),
    agentMatchList: document.querySelector("#agent-match-list"),
    agentGapList: document.querySelector("#agent-gap-list"),
    agentWarning: document.querySelector("#agent-warning"),
    opportunityCount: document.querySelector("#opportunity-count"),
    opportunityFreshness: document.querySelector("#opportunity-freshness"),
    opportunityList: document.querySelector("#opportunity-list"),
    refreshOpportunities: document.querySelector("#refresh-opportunities"),
    opportunitySearchForm: document.querySelector("#opportunity-search-form"),
    opportunityQuery: document.querySelector("#opportunity-query"),
    opportunityCompany: document.querySelector("#opportunity-company"),
    opportunityLocation: document.querySelector("#opportunity-location"),
    agentUseFeed: document.querySelector("#agent-use-feed"),
    agentJobs: document.querySelector("#agent-jobs"),
    chatToggle: document.querySelector("#chat-toggle"),
    chatPanel: document.querySelector("#chat-panel"),
    chatClose: document.querySelector("#chat-close"),
    chatForm: document.querySelector("#chat-form"),
    chatLog: document.querySelector("#chat-log"),
    chatMessage: document.querySelector("#chat-message"),
};

const reasonLabels = {
    graduation_year: "毕业年份不符合",
    education: "学历未达到要求",
    experience: "工作经验不足",
    location: "意向地点不匹配",
};

function commaValues(value) {
    return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
}

function optionalNumber(value) {
    return value === "" ? null : Number(value);
}

async function fileToBase64(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    for (let offset = 0; offset < bytes.length; offset += 0x8000) {
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
    }
    return btoa(binary);
}

function textToBase64(text) {
    const bytes = new TextEncoder().encode(text);
    let binary = "";
    for (let offset = 0; offset < bytes.length; offset += 0x8000) {
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
    }
    return btoa(binary);
}

function setRunState(message, kind = "") {
    elements.runState.className = `run-state ${kind}`;
    elements.runState.querySelector("span:last-child").textContent = message;
}

function setStep(step, complete = false) {
    const item = document.querySelector(`[data-step="${step}"]`);
    item.classList.toggle("complete", complete);
    item.classList.toggle("active", !complete);
}

function updateMatchButton(announceReady = true) {
    const ready = Boolean(state.candidateId && state.jobId);
    elements.runMatch.disabled = !ready;
    if (ready) {
        setStep("match");
        if (announceReady) setRunState("可以运行匹配", "ready");
    }
}

function resetResult() {
    elements.resultTitle.textContent = "等待分析";
    elements.resultSummary.textContent = "候选人画像与目标岗位保存后，即可运行硬条件匹配。";
    elements.reasonList.replaceChildren();
    elements.runMatch.textContent = "运行匹配";
    document.querySelector('[data-step="match"]').classList.remove("complete");
}

function clearExtraction(clearConstraints = false) {
    elements.evidenceList.replaceChildren();
    elements.extractionWarning.textContent = "";
    elements.evidencePanel.hidden = true;
    elements.extractConstraints.textContent = "从描述提取硬条件";
    state.extractionApplied = false;
    if (clearConstraints) {
        document.querySelector("#required-years").value = "";
        document.querySelector("#minimum-education").value = "";
        document.querySelector("#minimum-experience").value = "";
        document.querySelector("#job-locations").value = "";
    }
}

function markUnsaved(kind) {
    state.revision += 1;
    state[`${kind}Id`] = null;
    const status = document.querySelector(`#${kind === "candidate" ? "profile" : "job"}-status`);
    status.textContent = "有修改";
    status.classList.remove("saved");
    resetResult();
    updateMatchButton();
    setRunState("内容已修改，请重新保存");
}

function resetWorkbench() {
    state.revision += 1;
    state.candidateId = null;
    state.jobId = null;
    elements.profileForm.reset();
    elements.jobForm.reset();
    clearExtraction();
    elements.extractConstraints.disabled = false;
    elements.extractConstraints.textContent = "从描述提取硬条件";
    document.querySelector("#profile-status").textContent = "未保存";
    document.querySelector("#job-status").textContent = "未保存";
    document.querySelector("#profile-status").classList.remove("saved");
    document.querySelector("#job-status").classList.remove("saved");
    document.querySelectorAll(".step-track li").forEach((item) => {
        item.classList.remove("active", "complete");
    });
    document.querySelector('[data-step="profile"]').classList.add("active");
    resetResult();
    updateMatchButton();
    setRunState("等待输入");
}

function renderExtraction(extraction) {
    const constraints = extraction.constraints;
    document.querySelector("#required-years").value = constraints.graduation_years.join(", ");
    document.querySelector("#minimum-education").value = constraints.minimum_education || "";
    document.querySelector("#minimum-experience").value = constraints.minimum_years_of_experience ?? "";
    document.querySelector("#job-locations").value = constraints.locations.join(", ");

    const evidence = extraction.evidence;
    const items = [
        ...evidence.graduation_years,
        evidence.minimum_education,
        evidence.minimum_years_of_experience,
        ...evidence.locations,
    ].filter(Boolean);
    elements.evidenceList.replaceChildren();
    items.forEach((item) => {
        const listItem = document.createElement("li");
        listItem.textContent = item.text;
        elements.evidenceList.append(listItem);
    });
    elements.extractionWarning.textContent = extraction.warnings.join(" ");
    elements.evidencePanel.hidden = false;
    state.extractionApplied = true;
}

async function postJson(path, body) {
    const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const detail = Array.isArray(payload.detail)
            ? payload.detail.map((item) => item.msg).join("；")
            : payload.detail;
        throw new Error(detail || `请求失败 (${response.status})`);
    }
    return response.json();
}

async function getJson(path) {
    const response = await fetch(path);
    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `请求失败 (${response.status})`);
    }
    return response.json();
}

function formatRunLabel(run) {
    const timestamp = new Date(run.created_at).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
    return `${timestamp} · ${run.considered_jobs} 岗位 · ${run.state}`;
}

function appendTextItem(list, text, className = "") {
    const item = document.createElement("li");
    item.textContent = text;
    if (className) item.className = className;
    list.append(item);
}

function renderOpportunities(feed) {
    state.opportunities = feed.opportunities;
    elements.opportunityList.replaceChildren();
    elements.opportunityCount.textContent = `${feed.opportunities.length} 个岗位`;
    elements.opportunityFreshness.textContent = `历史核验快照 · ${feed.data_as_of} · ${feed.source_note}`;

    feed.opportunities.forEach((opportunity) => {
        const card = document.createElement("article");
        card.className = "opportunity-card";
        const heading = document.createElement("div");
        heading.className = "opportunity-card-heading";
        const company = document.createElement("span");
        company.className = "opportunity-company";
        company.textContent = opportunity.company;
        const direction = document.createElement("span");
        direction.className = "opportunity-direction";
        direction.textContent = opportunity.direction;
        heading.append(company, direction);

        const title = document.createElement("h3");
        title.textContent = opportunity.title;
        const meta = document.createElement("p");
        meta.className = "opportunity-meta";
        meta.textContent = `${opportunity.location} · 核验于 ${opportunity.last_verified_at}`;
        const highlights = document.createElement("ul");
        highlights.className = "opportunity-highlights";
        opportunity.highlights.forEach((highlight) => appendTextItem(highlights, highlight));
        const link = document.createElement("a");
        link.className = "opportunity-link";
        link.href = opportunity.source_url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = "打开官网复核";
        card.append(heading, title, meta, highlights, link);
        elements.opportunityList.append(card);
    });
}

function renderOpportunitySearch(result) {
    const successfulSources = result.sources.filter((source) => source.status === "success").length;
    const capturedDates = result.leads.map((lead) => lead.captured_at.slice(0, 10));
    renderOpportunities({
        data_as_of: capturedDates.length ? capturedDates.sort().at(-1) : "无结果",
        source_note: `${successfulSources} 个来源正常，${result.sources.length - successfulSources} 个来源异常`,
        opportunities: result.leads.map((lead) => ({
            opportunity_id: lead.external_id,
            company: lead.company,
            title: lead.title,
            location: lead.locations.join("、"),
            direction: lead.direction,
            source_url: lead.source_url,
            last_verified_at: lead.captured_at.slice(0, 10),
            verification_status: lead.verification_status,
            highlights: lead.highlights,
        })),
    });
}

async function loadOpportunities() {
    elements.refreshOpportunities.disabled = true;
    elements.refreshOpportunities.textContent = "加载中...";
    try {
        renderOpportunities(await getJson("/opportunities"));
    } catch (error) {
        state.opportunities = [];
        elements.opportunityCount.textContent = "加载失败";
        elements.opportunityFreshness.textContent = error.message;
        elements.opportunityList.replaceChildren();
    } finally {
        elements.refreshOpportunities.disabled = false;
        elements.refreshOpportunities.textContent = "刷新";
    }
}

function opportunityCatalog() {
    const sections = state.opportunities.map((opportunity, index) => [
        `### ${index + 1}. ${opportunity.title} | ${opportunity.company}`,
        "",
        "**基本信息**",
        "",
        `- 地点：${opportunity.location}`,
        `- 方向：${opportunity.direction}`,
        "",
        "**岗位职责**",
        "",
        `- ${opportunity.direction} 相关岗位，申请前需打开官网复核完整职责。`,
        "",
        "**任职要求**",
        "",
        ...opportunity.highlights.map((highlight) => `- ${highlight}`),
        "",
        "**状态与来源**",
        "",
        `- 待官网复核：${opportunity.source_url}`,
    ].join("\n"));
    return `# Lina 岗位核验快照\n\n${sections.join("\n\n")}`;
}

function updateFeedMatchMode() {
    elements.agentJobs.disabled = elements.agentUseFeed.checked;
}

function toggleChat(open) {
    elements.chatPanel.hidden = !open;
    elements.chatToggle.setAttribute("aria-expanded", String(open));
    if (open) elements.chatMessage.focus();
}

function appendChatMessage(text, role) {
    const message = document.createElement("p");
    message.className = `chat-message ${role}-message`;
    message.textContent = text;
    elements.chatLog.append(message);
    elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
}

function renderHistory(runs) {
    state.historyRuns = runs;
    elements.historyList.replaceChildren();
    elements.baseRun.replaceChildren();
    elements.targetRun.replaceChildren();
    elements.diffPanel.hidden = true;
    elements.historyCount.textContent = runs.length ? `${runs.length} 次运行` : "暂无运行";
    elements.historyEmpty.hidden = runs.length > 0;
    elements.historyContent.hidden = runs.length === 0;

    runs.forEach((run, index) => {
        const label = formatRunLabel(run);
        [elements.baseRun, elements.targetRun].forEach((select) => {
            const option = document.createElement("option");
            option.value = run.run_id;
            option.textContent = label;
            select.append(option);
        });
        const item = document.createElement("li");
        const rank = document.createElement("span");
        rank.className = "history-rank";
        rank.textContent = String(index + 1).padStart(2, "0");
        const summary = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = label;
        const meta = document.createElement("span");
        meta.textContent = `${run.matches.length} 个结果 · ${run.gaps.length} 项缺口 · ${run.run_id.slice(-8)}`;
        summary.append(title, meta);
        item.append(rank, summary);
        elements.historyList.append(item);
    });

    if (runs.length > 1) {
        elements.targetRun.value = runs[0].run_id;
        elements.baseRun.value = runs[1].run_id;
    }
    updateCompareButton();
}

function updateCompareButton() {
    elements.compareRuns.disabled = !(
        elements.baseRun.value
        && elements.targetRun.value
        && elements.baseRun.value !== elements.targetRun.value
    );
}

function renderDiff(diff) {
    elements.diffFacts.replaceChildren();
    elements.rankingChanges.replaceChildren();
    elements.scoreChanges.replaceChildren();
    elements.gapChanges.replaceChildren();

    appendTextItem(
        elements.diffFacts,
        diff.candidate_document_changed ? "候选文档已更新" : "候选文档未变",
        diff.candidate_document_changed ? "changed" : "stable",
    );
    appendTextItem(
        elements.diffFacts,
        diff.job_catalog_document_changed ? "岗位目录已更新" : "岗位目录未变",
        diff.job_catalog_document_changed ? "changed" : "stable",
    );
    appendTextItem(
        elements.diffFacts,
        diff.confirmation_changed ? "确认事实已更新" : "确认事实未变",
        diff.confirmation_changed ? "changed" : "stable",
    );
    appendTextItem(
        elements.diffFacts,
        diff.plan_changed ? "行动计划已更新" : "行动计划未变",
        diff.plan_changed ? "changed" : "stable",
    );

    diff.ranking_changes.forEach((change) => {
        const movement = change.position_delta < 0
            ? `上升 ${Math.abs(change.position_delta)} 位`
            : `下降 ${change.position_delta} 位`;
        appendTextItem(
            elements.rankingChanges,
            `岗位 ${change.catalog_number} · ${change.base_position} → ${change.target_position} · ${movement}`,
        );
    });
    diff.added_catalog_numbers.forEach((number) => {
        appendTextItem(elements.rankingChanges, `新增岗位 ${number}`);
    });
    diff.removed_catalog_numbers.forEach((number) => {
        appendTextItem(elements.rankingChanges, `移除岗位 ${number}`);
    });
    diff.replaced_catalog_numbers.forEach((number) => {
        appendTextItem(elements.rankingChanges, `岗位 ${number} 已替换`);
    });
    if (!elements.rankingChanges.children.length) {
        appendTextItem(elements.rankingChanges, "排名未变", "muted-item");
    }

    diff.score_changes.forEach((change) => {
        const delta = change.score_delta >= 0
            ? `+${change.score_delta.toFixed(1)}`
            : change.score_delta.toFixed(1);
        appendTextItem(
            elements.scoreChanges,
            `岗位 ${change.catalog_number} · ${change.base_score.toFixed(1)} → ${change.target_score.toFixed(1)} · ${delta}`,
        );
    });
    if (!elements.scoreChanges.children.length) {
        appendTextItem(elements.scoreChanges, "分数未变", "muted-item");
    }

    diff.added_gaps.forEach((skill) => appendTextItem(elements.gapChanges, `新增 ${skill}`));
    diff.resolved_gaps.forEach((skill) => appendTextItem(elements.gapChanges, `解决 ${skill}`));
    if (!elements.gapChanges.children.length) {
        appendTextItem(elements.gapChanges, "缺口未变", "muted-item");
    }
    elements.diffPanel.hidden = false;
}

function renderAgentRun(run) {
    elements.agentRunStatus.textContent = run.state;
    elements.agentRunStatus.classList.toggle("saved", run.state === "complete");
    elements.agentResultTitle.textContent = run.state === "complete" ? "运行完成" : "运行已结束";
    elements.agentMatchList.replaceChildren();
    elements.agentGapList.replaceChildren();

    run.matches.forEach((match) => {
        appendTextItem(
            elements.agentMatchList,
            `${match.title} · ${match.company} · ${match.score.toFixed(1)}`,
        );
    });
    if (!run.matches.length) appendTextItem(elements.agentMatchList, "没有可展示的匹配", "muted-item");

    run.gap_analysis.gaps.forEach((gap) => {
        appendTextItem(
            elements.agentGapList,
            `${gap.skill} · ${gap.priority} · 影响 ${gap.affected_catalog_numbers.length} 个岗位`,
        );
    });
    if (!run.gap_analysis.gaps.length) appendTextItem(elements.agentGapList, "没有聚合技能缺口", "muted-item");
    elements.agentWarning.textContent = run.warnings.join(" ");
    elements.agentResult.hidden = false;
}

function setSaving(form, saving) {
    const button = form.querySelector("button[type='submit']");
    button.disabled = saving;
    button.textContent = saving ? "正在保存..." : button.dataset.label;
}

elements.profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const revision = state.revision;
    const form = event.currentTarget;
    const button = form.querySelector("button[type='submit']");
    button.dataset.label ||= button.textContent;
    setSaving(form, true);
    setRunState("正在保存候选人");
    try {
        const profile = await postJson("/profiles", {
            graduation_year: Number(form.graduationYear.value),
            highest_education: form.education.value,
            years_of_experience: Number(form.experience.value),
            skills: commaValues(form.skills.value),
            preferred_locations: commaValues(form.locations.value),
        });
        if (state.revision !== revision) return;

        state.candidateId = profile.id;
        const status = document.querySelector("#profile-status");
        status.textContent = "已保存";
        status.classList.add("saved");
        setStep("profile", true);
        updateMatchButton();
        if (!state.jobId) setRunState("候选人已保存，请保存目标岗位", "ready");
    } catch (error) {
        if (state.revision !== revision) return;
        setRunState(error.message, "error");
    } finally {
        setSaving(form, false);
    }
});

elements.jobForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const revision = state.revision;
    const form = event.currentTarget;
    const button = form.querySelector("button[type='submit']");
    button.dataset.label ||= button.textContent;
    setSaving(form, true);
    setRunState("正在保存岗位");
    try {
        const job = await postJson("/jobs", {
            title: form.jobTitle.value,
            company: form.company.value,
            description: form.description.value,
            constraints: {
                minimum_education: form.minimumEducation.value || null,
                graduation_years: commaValues(form.requiredYears.value).map(Number),
                minimum_years_of_experience: optionalNumber(form.minimumExperience.value),
                locations: commaValues(form.jobLocations.value),
            },
        });
        if (state.revision !== revision) return;

        state.jobId = job.id;
        const status = document.querySelector("#job-status");
        status.textContent = "已保存";
        status.classList.add("saved");
        setStep("job", true);
        updateMatchButton();
        if (!state.candidateId) setRunState("岗位已保存，请保存候选人画像", "ready");
    } catch (error) {
        if (state.revision !== revision) return;
        setRunState(error.message, "error");
    } finally {
        setSaving(form, false);
    }
});

elements.extractConstraints.addEventListener("click", async () => {
    const description = document.querySelector("#description");
    if (!description.reportValidity()) return;
    if (state.extractionApplied) {
        clearExtraction(true);
        if (state.jobId) {
            markUnsaved("job");
        } else {
            state.revision += 1;
        }
    }
    const revision = state.revision;
    let extractionApplied = false;

    elements.extractConstraints.disabled = true;
    elements.extractConstraints.textContent = "正在提取...";
    setRunState("正在解析岗位描述");
    try {
        const extraction = await postJson("/jobs/parse", { description: description.value });
        if (state.revision !== revision) return;
        renderExtraction(extraction);
        markUnsaved("job");
        setRunState("提取完成，请人工确认", "ready");
        extractionApplied = true;
    } catch (error) {
        if (state.revision !== revision) return;
        setRunState(error.message, "error");
    } finally {
        elements.extractConstraints.disabled = false;
        elements.extractConstraints.textContent = extractionApplied
            ? "重新提取硬条件"
            : "从描述提取硬条件";
    }
});

elements.runMatch.addEventListener("click", async () => {
    const candidateId = state.candidateId;
    const jobId = state.jobId;
    elements.runMatch.disabled = true;
    elements.runMatch.textContent = "分析中...";
    elements.resultTitle.textContent = "分析中";
    elements.resultSummary.textContent = "正在核对毕业年份、学历、经验与地点要求。";
    elements.reasonList.replaceChildren();
    setRunState("正在运行硬条件匹配");
    try {
        const result = await postJson("/matches", {
            candidate_id: candidateId,
            job_id: jobId,
        });
        if (state.candidateId !== candidateId || state.jobId !== jobId) return;

        elements.reasonList.replaceChildren();
        if (result.is_eligible) {
            elements.resultTitle.textContent = "硬条件通过";
            elements.resultSummary.textContent = "当前画像满足岗位已声明的全部硬性要求，可以进入能力与证据分析。";
        } else {
            elements.resultTitle.textContent = "暂不满足硬条件";
            elements.resultSummary.textContent = `发现 ${result.reasons.length} 项明确门槛，请优先确认岗位批次或调整筛选范围。`;
            result.reasons.forEach((reason) => {
                const item = document.createElement("li");
                item.textContent = reasonLabels[reason] || reason;
                elements.reasonList.append(item);
            });
        }
        setStep("match", true);
        setRunState("匹配完成", "ready");
        elements.resultPanel.scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (error) {
        if (state.candidateId !== candidateId || state.jobId !== jobId) return;

        elements.resultTitle.textContent = "分析失败";
        elements.resultSummary.textContent = error.message;
        setRunState(error.message, "error");
    } finally {
        elements.runMatch.textContent = state.candidateId && state.jobId
            ? "重新匹配"
            : "运行匹配";
        updateMatchButton(false);
    }
});

async function loadHistory() {
    const revision = ++state.historyRevision;
    state.diffRevision += 1;
    elements.refreshHistory.disabled = true;
    elements.refreshHistory.textContent = "正在刷新...";
    elements.historyCount.textContent = "正在加载";
    elements.diffPanel.hidden = true;
    try {
        const runs = await getJson("/agent/runs?limit=20");
        if (state.historyRevision !== revision) return;
        renderHistory(runs);
        setRunState(runs.length ? "运行历史已更新" : "暂无 Agent Run", "ready");
    } catch (error) {
        if (state.historyRevision !== revision) return;
        elements.historyCount.textContent = "加载失败";
        elements.historyEmpty.hidden = false;
        elements.historyEmpty.textContent = error.message;
        elements.historyContent.hidden = true;
        setRunState(error.message, "error");
    } finally {
        if (state.historyRevision === revision) {
            elements.refreshHistory.disabled = false;
            elements.refreshHistory.textContent = "刷新历史";
        }
    }
}

elements.refreshHistory.addEventListener("click", loadHistory);
elements.refreshOpportunities.addEventListener("click", loadOpportunities);
elements.opportunitySearchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = elements.opportunitySearchForm.querySelector("button[type='submit']");
    button.disabled = true;
    button.textContent = "搜索中...";
    try {
        const result = await postJson("/opportunities/search", {
            query: elements.opportunityQuery.value.trim() || null,
            companies: elements.opportunityCompany.value
                ? [elements.opportunityCompany.value]
                : [],
            locations: commaValues(elements.opportunityLocation.value),
            max_results: 50,
        });
        renderOpportunitySearch(result);
    } catch (error) {
        elements.opportunityCount.textContent = "搜索失败";
        elements.opportunityFreshness.textContent = error.message;
    } finally {
        button.disabled = false;
        button.textContent = "搜索岗位";
    }
});
elements.agentUseFeed.addEventListener("change", updateFeedMatchMode);

elements.chatToggle.addEventListener("click", () => toggleChat(elements.chatPanel.hidden));
elements.chatClose.addEventListener("click", () => toggleChat(false));
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !elements.chatPanel.hidden) toggleChat(false);
});
elements.chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = elements.chatMessage.value.trim();
    if (!message) return;
    const button = elements.chatForm.querySelector("button[type='submit']");
    appendChatMessage(message, "user");
    elements.chatMessage.value = "";
    button.disabled = true;
    button.textContent = "发送中...";
    try {
        const response = await postJson("/assistant/messages", { message });
        appendChatMessage(response.answer, "assistant");
        if (response.suggested_action === "view_opportunities") {
            document.querySelector("#opportunities").scrollIntoView({ behavior: "smooth" });
        } else if (response.suggested_action === "upload_resume") {
            document.querySelector("#file-agent").scrollIntoView({ behavior: "smooth" });
        }
    } catch (error) {
        appendChatMessage(error.message, "assistant");
    } finally {
        button.disabled = false;
        button.textContent = "发送";
    }
});

elements.fileAgentForm.addEventListener("input", () => {
    state.agentRevision += 1;
    elements.agentResult.hidden = true;
    elements.agentRunStatus.textContent = "有修改";
    elements.agentRunStatus.classList.remove("saved");
});

elements.agentAutoSignals.addEventListener("change", () => {
    elements.agentConfirmations.disabled = !elements.agentAutoSignals.checked;
    elements.agentConfirmations.closest("details").open = elements.agentAutoSignals.checked;
    if (!elements.agentAutoSignals.checked) {
        elements.agentConfirmations.querySelectorAll("input").forEach((input) => {
            input.value = "";
        });
    }
});

elements.fileAgentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const revision = ++state.agentRevision;
    const form = event.currentTarget;
    const button = form.querySelector("button[type='submit']");
    const resume = document.querySelector("#agent-resume").files[0];
    const jobCatalog = elements.agentJobs.files[0];
    if (!resume || (!elements.agentUseFeed.checked && !jobCatalog)) return;
    if (elements.agentUseFeed.checked && !state.opportunities.length) {
        elements.agentRunStatus.textContent = "岗位快照未加载";
        return;
    }

    button.disabled = true;
    button.textContent = "正在运行...";
    elements.agentRunStatus.textContent = "运行中";
    elements.agentRunStatus.classList.remove("saved");
    elements.agentResult.hidden = true;
    setRunState("正在运行文件 Agent");
    try {
        const payload = {
            resume: { filename: resume.name, content: await fileToBase64(resume) },
            job_catalog: elements.agentUseFeed.checked
                ? { filename: "lina-opportunity-snapshots.md", content: textToBase64(opportunityCatalog()) }
                : { filename: jobCatalog.name, content: await fileToBase64(jobCatalog) },
            top_k: Number(document.querySelector("#agent-top-k").value),
            include_inactive: false,
            auto_decision_signals: elements.agentAutoSignals.checked,
            use_llm: document.querySelector("#agent-use-llm").checked,
        };
        if (payload.auto_decision_signals) {
            const weeklyDays = optionalNumber(document.querySelector("#agent-weekly-days").value);
            const durationMonths = optionalNumber(document.querySelector("#agent-duration-months").value);
            if (weeklyDays !== null || durationMonths !== null) {
                payload.candidate_availability = {};
                if (weeklyDays !== null) payload.candidate_availability.weekly_days = weeklyDays;
                if (durationMonths !== null) payload.candidate_availability.duration_months = durationMonths;
            }

            const directionFields = {
                agent_llm_application: "#direction-agent",
                ai_infrastructure: "#direction-infra",
                machine_learning: "#direction-ml",
                ai_product: "#direction-product",
                fullstack_ai_testing: "#direction-testing",
                risk_modeling: "#direction-risk",
            };
            const directions = {};
            Object.entries(directionFields).forEach(([name, selector]) => {
                const value = optionalNumber(document.querySelector(selector).value);
                if (value !== null) directions[name] = value;
            });
            if (Object.keys(directions).length) payload.candidate_direction_preferences = directions;
        }

        const run = await postJson("/agent/runs", payload);
        if (state.agentRevision !== revision) return;
        renderAgentRun(run);
        setRunState("文件 Agent 运行完成", "ready");
        await loadHistory();
    } catch (error) {
        if (state.agentRevision !== revision) return;
        elements.agentRunStatus.textContent = "运行失败";
        elements.agentResultTitle.textContent = "运行失败";
        elements.agentMatchList.replaceChildren();
        elements.agentGapList.replaceChildren();
        elements.agentWarning.textContent = error.message;
        elements.agentResult.hidden = false;
        setRunState(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "运行文件 Agent";
    }
});

[elements.baseRun, elements.targetRun].forEach((select) => {
    select.addEventListener("change", () => {
        state.diffRevision += 1;
        elements.diffPanel.hidden = true;
        updateCompareButton();
    });
});

elements.compareRuns.addEventListener("click", async () => {
    const baseRunId = elements.baseRun.value;
    const targetRunId = elements.targetRun.value;
    if (!baseRunId || !targetRunId || baseRunId === targetRunId) return;
    const revision = ++state.diffRevision;
    elements.compareRuns.disabled = true;
    elements.compareRuns.textContent = "正在比较...";
    setRunState("正在比较运行版本");
    try {
        const diff = await getJson(`/agent/runs/${baseRunId}/diff/${targetRunId}`);
        if (state.diffRevision !== revision) return;
        renderDiff(diff);
        setRunState("版本比较完成", "ready");
        elements.diffPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (error) {
        if (state.diffRevision !== revision) return;
        setRunState(error.message, "error");
    } finally {
        if (state.diffRevision === revision) {
            elements.compareRuns.textContent = "比较变化";
            updateCompareButton();
        }
    }
});

document.querySelector("#load-example").addEventListener("click", () => {
    resetWorkbench();
    document.querySelector("#graduation-year").value = "2028";
    document.querySelector("#education").value = "master";
    document.querySelector("#experience").value = "0.3";
    document.querySelector("#locations").value = "上海";
    document.querySelector("#skills").value = "Python, RAG, Agent, SQL, XGBoost";
    document.querySelector("#job-title").value = "Agent 研发工程师（2027 届）";
    document.querySelector("#company").value = "示例科技";
    document.querySelector("#minimum-education").value = "bachelor";
    document.querySelector("#required-years").value = "2027";
    document.querySelector("#minimum-experience").value = "";
    document.querySelector("#job-locations").value = "上海";
    document.querySelector("#description").value = "工作地点：上海。面向 2027 届毕业生，要求本科及以上学历。参与 Agent 系统设计与研发，负责任务规划、上下文构建、多工具调用编排与结果验证。";
    setRunState("示例已载入，请依次保存", "ready");
    elements.profileForm.scrollIntoView({ behavior: "smooth", block: "start" });
});

elements.resetWorkbench.addEventListener("click", () => {
    resetWorkbench();
    window.scrollTo({ top: 0, behavior: "smooth" });
});

elements.profileForm.addEventListener("input", () => {
    if (state.candidateId) {
        markUnsaved("candidate");
    } else {
        state.revision += 1;
        setRunState("内容已修改，请保存");
    }
});

elements.jobForm.addEventListener("input", (event) => {
    if (event.target.id === "description" && state.extractionApplied) {
        clearExtraction(true);
    }
    if (state.jobId) {
        markUnsaved("job");
    } else {
        state.revision += 1;
        setRunState("内容已修改，请保存");
    }
});

updateFeedMatchMode();
loadOpportunities();