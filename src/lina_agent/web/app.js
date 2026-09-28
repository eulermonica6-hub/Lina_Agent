const state = {
    candidateId: null,
    jobId: null,
    revision: 0,
    extractionApplied: false,
    historyRevision: 0,
    diffRevision: 0,
    historyRuns: [],
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

elements.refreshHistory.addEventListener("click", async () => {
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