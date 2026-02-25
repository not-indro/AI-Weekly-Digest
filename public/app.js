/* ============================================
   AI This Week — Frontend Logic
   ============================================ */

const SECTIONS = [
    { key: "trending", label: "Trending AI" },
    { key: "indian", label: "Indian News" },
    { key: "global", label: "Global News" },
    { key: "events", label: "Events" },
    { key: "ai_progress", label: "AI Progress" },
    { key: "research_plain", label: "AI Research" },
    { key: "deep_dive", label: "Deep Dive" },
];

/* ── Section Defaults (mirrors DEFAULT_STREAMS in search.py) ── */

const SECTION_DEFAULTS = {
    trending: { threshold: 7, days: null, limit: 8 },
    indian: { threshold: 6, days: null, limit: 5 },
    global: { threshold: 6, days: null, limit: 5 },
    events: { threshold: 5, days: null, limit: 4 },
    ai_progress: { threshold: 6, days: 14, limit: 3 },
    research_plain: { threshold: 5, days: 14, limit: 3 },
    deep_dive: { threshold: 7, days: 14, limit: 2 },
};

/* ── Config Profiles ── */

const PROFILES = {
    strict: {
        trending: { threshold: 8, days: null, limit: 5 },
        indian: { threshold: 7, days: null, limit: 4 },
        global: { threshold: 7, days: null, limit: 4 },
        events: { threshold: 6, days: null, limit: 3 },
        ai_progress: { threshold: 7, days: 14, limit: 2 },
        research_plain: { threshold: 7, days: 14, limit: 2 },
        deep_dive: { threshold: 8, days: 14, limit: 1 },
    },
    balanced: { ...structuredClone(SECTION_DEFAULTS) },
    exploratory: {
        trending: { threshold: 5, days: null, limit: 12 },
        indian: { threshold: 4, days: null, limit: 8 },
        global: { threshold: 4, days: null, limit: 8 },
        events: { threshold: 3, days: null, limit: 6 },
        ai_progress: { threshold: 4, days: 21, limit: 5 },
        research_plain: { threshold: 4, days: 21, limit: 5 },
        deep_dive: { threshold: 5, days: 21, limit: 4 },
    },
};

// Copy balanced from defaults
Object.keys(SECTION_DEFAULTS).forEach(k => {
    PROFILES.balanced[k] = { ...SECTION_DEFAULTS[k] };
});

let generatedHTML = null;
let _startTime = null;
let _timerInterval = null;
let _sectionTimes = [];   // track how long each section takes
let _tuningOpen = false;

/* ── Helpers ────────────────────────────── */

function $(id) { return document.getElementById(id); }

function setVisible(id, show) {
    $(id).style.display = show ? "" : "none";
}

function setChipState(key, state) {
    const chip = document.querySelector(`[data-key="${key}"]`);
    if (!chip) return;
    chip.className = "section-chip " + state;

    const iconEl = chip.querySelector(".chip-icon");
    if (state === "active") {
        iconEl.innerHTML = '<div class="spinner"></div>';
    } else if (state === "done") {
        iconEl.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20,6 9,17 4,12"/></svg>';
    } else if (state === "error") {
        iconEl.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    }
}

/* ── Tuning Panel ──────────────────────── */

function initTuningGrid() {
    const grid = $("tuning-grid");
    grid.innerHTML = SECTIONS.map(s => {
        const d = SECTION_DEFAULTS[s.key] || { threshold: 6, days: null, limit: 5 };
        return `
        <div class="tuning-row" data-section="${s.key}">
            <span class="tuning-label">${s.label}</span>
            <div class="tuning-control">
                <label class="tuning-mini-label">Relevance</label>
                <input type="range" min="1" max="10" value="${d.threshold}"
                       class="tuning-slider" id="threshold-${s.key}"
                       oninput="this.nextElementSibling.textContent=this.value">
                <span class="tuning-value">${d.threshold}</span>
            </div>
            <div class="tuning-control">
                <label class="tuning-mini-label">Days</label>
                <input type="number" min="1" max="30" value="${d.days || ''}"
                       placeholder="—" class="tuning-input" id="days-${s.key}">
            </div>
            <div class="tuning-control">
                <label class="tuning-mini-label">Limit</label>
                <input type="number" min="1" max="20" value="${d.limit}"
                       class="tuning-input" id="limit-${s.key}">
            </div>
        </div>`;
    }).join("");
}

function toggleTuning() {
    _tuningOpen = !_tuningOpen;
    $("tuning-content").style.display = _tuningOpen ? "" : "none";
    $("tuning-chevron").style.transform = _tuningOpen ? "rotate(180deg)" : "";
}

function applyProfile() {
    const profileKey = $("profile-select").value;
    const profile = PROFILES[profileKey];
    if (!profile) return;

    SECTIONS.forEach(s => {
        const cfg = profile[s.key];
        if (!cfg) return;
        const threshEl = $(`threshold-${s.key}`);
        const daysEl = $(`days-${s.key}`);
        const limitEl = $(`limit-${s.key}`);
        if (threshEl) {
            threshEl.value = cfg.threshold;
            threshEl.nextElementSibling.textContent = cfg.threshold;
        }
        if (daysEl) daysEl.value = cfg.days || "";
        if (limitEl) limitEl.value = cfg.limit;
    });
}

function getTuningOverrides(sectionKey) {
    const threshold = $(`threshold-${sectionKey}`)?.value;
    const days = $(`days-${sectionKey}`)?.value;
    const limit = $(`limit-${sectionKey}`)?.value;
    return {
        threshold: threshold ? parseInt(threshold) : null,
        days: days ? parseInt(days) : null,
        limit: limit ? parseInt(limit) : null,
    };
}

/* ── Progress UI ────────────────────────── */

function initProgress() {
    const grid = $("section-status");
    grid.innerHTML = SECTIONS.map(s =>
        `<div class="section-chip" data-key="${s.key}">
            <span class="chip-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" opacity="0.4"><circle cx="12" cy="12" r="10"/></svg>
            </span>
            <span>${s.label}</span>
        </div>`
    ).join("");

    $("progress-bar").style.width = "0%";
    $("progress-pct").textContent = "0%";
    $("progress-count").textContent = `0 / ${SECTIONS.length}`;
    $("progress-text").textContent = "Starting generation…";
    $("progress-time").textContent = "Est. 3–5 min";
    setVisible("progress-container", true);
    setVisible("error-container", false);
    setVisible("result-container", false);

    // Start elapsed timer
    _startTime = Date.now();
    _sectionTimes = [];
    if (_timerInterval) clearInterval(_timerInterval);
    _timerInterval = setInterval(_updateTimer, 1000);
}

function _formatTime(ms) {
    const totalSec = Math.floor(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
}

function _updateTimer() {
    if (!_startTime) return;
    const elapsed = Date.now() - _startTime;
    const done = _sectionTimes.length;
    const remaining = SECTIONS.length - done;

    let timeText = `Elapsed: ${_formatTime(elapsed)}`;
    if (done > 0 && remaining > 0) {
        const avgPerSection = elapsed / done;
        const estRemaining = avgPerSection * remaining;
        timeText += ` · ~${_formatTime(estRemaining)} remaining`;
    } else if (remaining === 0) {
        timeText = `Completed in ${_formatTime(elapsed)}`;
        if (_timerInterval) { clearInterval(_timerInterval); _timerInterval = null; }
    }
    $("progress-time").textContent = timeText;
}

function updateProgress(completed, currentLabel) {
    const pct = Math.round((completed / SECTIONS.length) * 100);
    $("progress-bar").style.width = pct + "%";
    $("progress-pct").textContent = pct + "%";
    $("progress-count").textContent = `${completed} / ${SECTIONS.length}`;
    $("progress-text").textContent = currentLabel
        ? `Generating: ${currentLabel}…`
        : "Complete!";
}

/* ── Generate ───────────────────────────── */

async function generateNewsletter() {
    const globalDays = parseInt($("days-input").value) || 7;
    const lang = $("lang-select").value || "en";
    const generateBtn = $("generate-btn");
    const downloadBtn = $("download-btn");
    const copyBtn = $("copyToClipboardBtn");
    const shareBtn = $("shareEmailBtn");

    generateBtn.disabled = true;
    downloadBtn.disabled = true;
    if (copyBtn) copyBtn.disabled = true;
    if (shareBtn) shareBtn.disabled = true;
    generatedHTML = null;

    initProgress();

    const allSections = {};
    let completed = 0;
    let hasErrors = false;
    let _sectionStart = Date.now();

    // Rate-limit delay helper (Gemini free tier: ~15 RPM)
    const RATE_LIMIT_DELAY_MS = 15000;
    const sleep = (ms) => new Promise(r => setTimeout(r, ms));

    for (let si = 0; si < SECTIONS.length; si++) {
        const section = SECTIONS[si];
        setChipState(section.key, "active");
        updateProgress(completed, section.label);

        // Build query params with tuning overrides
        const overrides = getTuningOverrides(section.key);
        const sectionDays = overrides.days || globalDays;

        try {
            // ── Step 1: Search (fast, no LLM) ──
            let searchUrl = `/api/search_section?key=${section.key}&days=${sectionDays}&lang=${lang}`;
            if (overrides.limit) searchUrl += `&limit=${overrides.limit}`;

            const searchResp = await fetch(searchUrl);
            if (!searchResp.ok) {
                const err = await searchResp.json().catch(() => ({ error: searchResp.statusText }));
                throw new Error(err.error || `Search HTTP ${searchResp.status}`);
            }

            const searchData = await searchResp.json();

            if (searchData.error) {
                throw new Error(searchData.error);
            }

            if (!searchData.articles || searchData.articles.length === 0) {
                allSections[section.key] = [];
                setChipState(section.key, "done");
                completed++;
                _sectionTimes.push(Date.now() - _sectionStart);
                _sectionStart = Date.now();
                _updateTimer();
                updateProgress(completed, completed < SECTIONS.length ? SECTIONS[completed]?.label : null);
                continue;
            }

            // ── Step 2: Summarize with LLM ──
            const summarizeOnce = async () => {
                const sumResp = await fetch("/api/summarize_section", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        key: section.key,
                        section_name: section.label,
                        lang: lang,
                        days: sectionDays,
                        relevance_threshold: overrides.threshold || 6,
                        articles: searchData.articles,
                    }),
                });

                if (!sumResp.ok) {
                    const err = await sumResp.json().catch(() => ({ error: sumResp.statusText }));
                    throw new Error(err.error || `Summarize HTTP ${sumResp.status}`);
                }

                return await sumResp.json();
            };

            let data = await summarizeOnce();

            // If rate-limited (error contains "429"), wait and retry once
            if (data.error && data.error.includes("429")) {
                console.warn(`Section ${section.key} rate-limited. Waiting ${RATE_LIMIT_DELAY_MS / 1000}s and retrying...`);
                $("progress-text").textContent = `Rate limited — cooling down (${RATE_LIMIT_DELAY_MS / 1000}s)…`;
                await sleep(RATE_LIMIT_DELAY_MS);
                data = await summarizeOnce();
            }

            allSections[section.key] = data.items || [];

            if (data.error) {
                console.error(`Section ${section.key} failed:`, data.error);
                setChipState(section.key, "error");
                allSections[section.key] = [];
                hasErrors = true;

                if (data.error.includes("Missing") && !window._configAlertShown) {
                    alert(data.error);
                    window._configAlertShown = true;
                }
            } else if (data.items && data.items.length === 0) {
                setChipState(section.key, "done");
            } else {
                setChipState(section.key, "done");
            }
        } catch (err) {
            console.error(`Section ${section.key} failed:`, err);
            setChipState(section.key, "error");
            allSections[section.key] = [];
            hasErrors = true;
        }

        completed++;
        _sectionTimes.push(Date.now() - _sectionStart);
        _updateTimer();
        updateProgress(completed, completed < SECTIONS.length ? SECTIONS[completed]?.label : null);

        // ── Rate-limit cooldown between sections (skip after last) ──
        if (si < SECTIONS.length - 1) {
            const nextLabel = SECTIONS[si + 1]?.label || "next section";
            for (let countdown = Math.ceil(RATE_LIMIT_DELAY_MS / 1000); countdown > 0; countdown--) {
                $("progress-text").textContent = `Cooling down before ${nextLabel}… ${countdown}s`;
                await sleep(1000);
            }
        }
        // Reset section start AFTER cooldown so next section timing is clean
        _sectionStart = Date.now();
    }

    // Render the full newsletter
    $("progress-text").textContent = "Rendering newsletter…";

    try {
        const today = new Date().toISOString().slice(0, 10);

        // Collect top-relevance items for TL;DR
        const allItems = Object.values(allSections).flat();
        allItems.sort((a, b) => (b.Relevance || 0) - (a.Relevance || 0));
        const topItems = allItems.slice(0, 6);

        // Generate TL;DR via server
        let tldr = [];
        if (topItems.length > 0) {
            try {
                const tldrResp = await fetch("/api/tldr", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ items: topItems, lang: lang }),
                });
                if (tldrResp.ok) {
                    const tldrData = await tldrResp.json();
                    tldr = tldrData.tldr || [];
                }
            } catch (e) {
                console.warn("TL;DR generation failed, continuing without it", e);
            }
        }

        const renderResp = await fetch("/api/render", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sections: allSections, run_date: today, tldr: tldr, lang: lang }),
        });

        if (!renderResp.ok) {
            throw new Error(`Render failed: HTTP ${renderResp.status}`);
        }

        generatedHTML = await renderResp.text();

        // Display in iframe
        const frame = $("newsletter-frame");
        frame.srcdoc = generatedHTML;
        $("result-date").textContent = today;
        setVisible("result-container", true);
        downloadBtn.disabled = false;
        if (copyBtn) copyBtn.disabled = false;
        if (shareBtn) shareBtn.disabled = false;

        updateProgress(SECTIONS.length, null);
        $("progress-text").textContent = hasErrors
            ? "Done with some errors — check highlighted sections"
            : "✓ Newsletter generated successfully!";

    } catch (err) {
        $("error-text").textContent = `Render error: ${err.message}`;
        setVisible("error-container", true);
    }

    generateBtn.disabled = false;
}

/* ── Download ───────────────────────────── */

function downloadHTML() {
    if (!generatedHTML) return;

    const blob = new Blob([generatedHTML], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ai-weekly-digest-${new Date().toISOString().slice(0, 10)}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

async function copyToClipboard() {
    if (!generatedHTML) return;
    try {
        const typeHtml = "text/html";
        const typeText = "text/plain";

        const tempDiv = document.createElement("div");
        tempDiv.innerHTML = generatedHTML;
        const textContent = tempDiv.innerText;

        const blobHtml = new Blob([generatedHTML], { type: typeHtml });
        const blobText = new Blob([textContent], { type: typeText });

        const data = [new ClipboardItem({
            [typeHtml]: blobHtml,
            [typeText]: blobText,
        })];

        await navigator.clipboard.write(data);

        const btn = $("copyToClipboardBtn");
        const origText = btn.innerHTML;
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!`;
        setTimeout(() => { btn.innerHTML = origText; }, 2000);
    } catch (err) {
        console.error("Failed to copy", err);
        alert("Failed to copy to clipboard. Ensure you are on HTTPS.");
    }
}

function shareViaEmail() {
    if (!generatedHTML) return;
    const subject = encodeURIComponent(`AI Weekly Digest - ${new Date().toISOString().slice(0, 10)}`);
    const body = encodeURIComponent("I generated this AI briefing. Copy and paste the rich text digest here:\n\n");
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
}

/* ── Init ───────────────────────────────── */

document.addEventListener("DOMContentLoaded", () => {
    initTuningGrid();
});
