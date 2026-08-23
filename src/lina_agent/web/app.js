const state = { candidateId: null, jobId: null, revision: 0, extractionApplied: false };

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