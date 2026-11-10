const elements = {
    kind: document.querySelector("#inbox-kind"),
    status: document.querySelector("#inbox-status"),
    refresh: document.querySelector("#inbox-refresh"),
    feedback: document.querySelector("#inbox-feedback"),
    list: document.querySelector("#inbox-list"),
    total: document.querySelector("#inbox-total"),
    monitorStatus: document.querySelector("#monitor-status"),
};

const kindLabels = {
    new: "新增",
    updated: "已更新",
    closed: "已关闭",
    reopened: "重新开放",
};

async function requestJson(path, options = {}) {
    const response = await fetch(path, options);
    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `请求失败 (${response.status})`);
    }
    return response.json();
}

function createFlag(label, field, checked, eventId) {
    const wrapper = document.createElement("label");
    wrapper.className = "inbox-flag";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = checked;
    input.addEventListener("change", async () => {
        input.disabled = true;
        try {
            await requestJson(`/inbox/events/${eventId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ [field]: input.checked }),
            });
            await loadInbox();
        } catch (error) {
            input.checked = !input.checked;
            elements.feedback.textContent = error.message;
        } finally {
            input.disabled = false;
        }
    });
    const text = document.createElement("span");
    text.textContent = label;
    wrapper.append(input, text);
    return wrapper;
}

function renderInbox(items) {
    elements.list.replaceChildren();
    elements.total.textContent = `${items.length} 条动态`;
    if (!items.length) {
        const empty = document.createElement("p");
        empty.className = "inbox-empty";
        empty.textContent = "当前筛选下没有岗位动态。";
        elements.list.append(empty);
        return;
    }

    items.forEach((item) => {
        const card = document.createElement("article");
        card.className = "inbox-item";
        const heading = document.createElement("div");
        heading.className = "inbox-item-heading";
        const kind = document.createElement("span");
        kind.className = `inbox-kind inbox-kind-${item.kind}`;
        kind.textContent = kindLabels[item.kind];
        const time = document.createElement("time");
        time.dateTime = item.occurred_at;
        time.textContent = new Date(item.occurred_at).toLocaleString("zh-CN", {
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
        });
        heading.append(kind, time);

        const title = document.createElement("h2");
        title.textContent = item.title;
        const meta = document.createElement("p");
        meta.className = "inbox-item-meta";
        meta.textContent = `NVIDIA · ${item.external_id}`;
        const actions = document.createElement("div");
        actions.className = "inbox-item-actions";
        actions.append(
            createFlag("收藏", "saved", item.saved, item.event_id),
            createFlag("待比较", "compare_later", item.compare_later, item.event_id),
            createFlag("忽略", "ignored", item.ignored, item.event_id),
        );
        const link = document.createElement("a");
        link.className = "opportunity-link";
        link.href = item.source_url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = "打开官方岗位";
        card.append(heading, title, meta, actions, link);
        elements.list.append(card);
    });
}

async function loadInbox() {
    elements.refresh.disabled = true;
    elements.feedback.textContent = "";
    const parameters = new URLSearchParams({ status: elements.status.value });
    if (elements.kind.value) parameters.set("kind", elements.kind.value);
    try {
        const [items, status] = await Promise.all([
            requestJson(`/inbox/events?${parameters}`),
            requestJson("/inbox/events/status"),
        ]);
        renderInbox(items);
        renderMonitorStatus(status);
    } catch (error) {
        elements.total.textContent = "加载失败";
        elements.feedback.textContent = error.message;
        elements.list.replaceChildren();
    } finally {
        elements.refresh.disabled = false;
    }
}

async function refreshMonitoring() {
    elements.refresh.disabled = true;
    elements.feedback.textContent = "正在检查 NVIDIA 官方岗位…";
    try {
        const result = await requestJson("/inbox/events/refresh", { method: "POST" });
        elements.feedback.textContent =
            `检查完成：${result.current_job_count} 个开放岗位，新增 ${result.new_event_count} 条动态。`;
        await loadInbox();
    } catch (error) {
        elements.feedback.textContent = `检查失败：${error.message}`;
        elements.refresh.disabled = false;
    }
}

function renderMonitorStatus(status) {
    if (!status.baseline_ready) {
        elements.monitorStatus.textContent = "尚未完成首次检查，请运行 Lina weekly monitor。";
        return;
    }
    const checkedAt = new Date(status.last_checked_at).toLocaleString("zh-CN");
    const eventText = status.event_count
        ? `累计 ${status.event_count} 条变化`
        : "两次检查之间尚未发现变化";
    elements.monitorStatus.textContent =
        `${status.source_name}：最近检查 ${checkedAt}，当前 ${status.current_job_count} 个开放岗位；${eventText}。`;
}

elements.kind.addEventListener("change", loadInbox);
elements.status.addEventListener("change", loadInbox);
elements.refresh.addEventListener("click", refreshMonitoring);
loadInbox();
