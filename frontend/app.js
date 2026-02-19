/* ═══════════════════════════════════════════════════════════════════
   MedAgent-Pro — Frontend Application Logic
   ═══════════════════════════════════════════════════════════════════ */

(() => {
    'use strict';

    // ── DOM refs ──────────────────────────────────────────────────

    const $  = (s) => document.querySelector(s);
    const $$ = (s) => document.querySelectorAll(s);

    const navBtns         = $$('.nav-btn');
    const viewDiagnose    = $('#view-diagnose');
    const viewHistory     = $('#view-history');
    const dashboard       = $('#results-dashboard');
    const diagForm        = $('#diagnosis-form');
    const submitBtn       = $('#submit-btn');
    const btnText         = submitBtn.querySelector('.btn-text');
    const btnLoader       = submitBtn.querySelector('.btn-loader');
    const diseaseInput    = $('#disease-input');
    const suggestionsBox  = $('#disease-suggestions');
    const imageInput      = $('#image-input');
    const uploadArea      = $('#file-upload-area');
    const uploadPlaceholder = $('#upload-placeholder');
    const uploadPreview   = $('#upload-preview');
    const previewImg      = $('#preview-img');
    const removeImageBtn  = $('#remove-image');
    const resultsList     = $('#results-list');
    const backBtn         = $('#back-btn');
    const dashTitle       = $('#dashboard-title');
    const dashBadge       = $('#dashboard-badge');

    let pipelineGraph = null;
    let findingsGraph = null;

    // ── Navigation ───────────────────────────────────────────────

    function switchView(view) {
        navBtns.forEach(b => b.classList.toggle('active', b.dataset.view === view));
        viewDiagnose.classList.toggle('active', view === 'diagnose');
        viewHistory.classList.toggle('active', view === 'history');
        dashboard.style.display = 'none';

        if (view === 'history') loadHistory();
    }

    navBtns.forEach(btn => {
        btn.addEventListener('click', () => switchView(btn.dataset.view));
    });

    backBtn.addEventListener('click', () => {
        dashboard.style.display = 'none';
        viewHistory.classList.add('active');
    });

    // ── Image upload ─────────────────────────────────────────────

    imageInput.addEventListener('change', () => {
        const file = imageInput.files[0];
        if (!file) return;
        const url = URL.createObjectURL(file);
        previewImg.src = url;
        uploadPlaceholder.style.display = 'none';
        uploadPreview.style.display = 'flex';
    });

    removeImageBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        imageInput.value = '';
        uploadPlaceholder.style.display = '';
        uploadPreview.style.display = 'none';
        previewImg.src = '';
    });

    ['dragenter', 'dragover'].forEach(ev => {
        uploadArea.addEventListener(ev, (e) => { e.preventDefault(); uploadArea.classList.add('dragover'); });
    });
    ['dragleave', 'drop'].forEach(ev => {
        uploadArea.addEventListener(ev, () => uploadArea.classList.remove('dragover'));
    });

    // ── Disease suggestions ──────────────────────────────────────

    async function loadDiseases() {
        try {
            const res = await fetch('/api/diseases');
            const diseases = await res.json();
            suggestionsBox.innerHTML = '';
            for (const d of diseases) {
                const tag = document.createElement('span');
                tag.className = 'suggestion';
                tag.textContent = d.disease || d.name;
                tag.addEventListener('click', () => {
                    diseaseInput.value = d.disease || d.name;
                    diseaseInput.focus();
                });
                suggestionsBox.appendChild(tag);
            }
        } catch { /* silent */ }
    }

    // ── Form submission ──────────────────────────────────────────

    diagForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (submitBtn.disabled) return;

        submitBtn.disabled = true;
        btnText.textContent = 'Analyzing…';
        btnLoader.style.display = '';

        const formData = new FormData(diagForm);

        try {
            const res = await fetch('/api/diagnose', { method: 'POST', body: formData });
            const data = await res.json();

            if (!res.ok) {
                alert('Error: ' + (data.error || 'Unknown error'));
                return;
            }

            showDashboard(data, formData.get('disease'));
        } catch (err) {
            alert('Network error: ' + err.message);
        } finally {
            submitBtn.disabled = false;
            btnText.textContent = 'Run Diagnosis';
            btnLoader.style.display = 'none';
        }
    });

    // ── History ──────────────────────────────────────────────────

    async function loadHistory() {
        resultsList.innerHTML = '<p class="placeholder-text">Loading…</p>';
        try {
            const res = await fetch('/api/results');
            const results = await res.json();

            if (!results.length) {
                resultsList.innerHTML = '<p class="placeholder-text">No past diagnoses found.</p>';
                return;
            }

            resultsList.innerHTML = '';
            for (const r of results) {
                const item = document.createElement('div');
                item.className = 'result-item';
                item.innerHTML = `
                    <div class="result-icon">🔬</div>
                    <div class="result-info">
                        <div class="disease-name">${r.disease.replace(/_/g, ' ')}</div>
                        <div class="record-meta">${r.record} · ${r.start_time ? new Date(r.start_time).toLocaleDateString() : '—'}</div>
                    </div>
                    <span class="result-arrow">→</span>
                `;
                item.addEventListener('click', () => loadResult(r.disease, r.record));
                resultsList.appendChild(item);
            }
        } catch {
            resultsList.innerHTML = '<p class="placeholder-text">Failed to load history.</p>';
        }
    }

    async function loadResult(disease, record) {
        try {
            const res = await fetch(`/api/results/${disease}/${record}`);
            const data = await res.json();
            showDashboard(data, disease.replace(/_/g, ' '));
        } catch {
            alert('Failed to load result.');
        }
    }

    // ── Dashboard ────────────────────────────────────────────────

    function showDashboard(data, disease) {
        viewDiagnose.classList.remove('active');
        viewHistory.classList.remove('active');
        navBtns.forEach(b => b.classList.remove('active'));
        dashboard.style.display = '';

        dashTitle.textContent = disease || 'Diagnosis Results';

        const diag = data.final_diagnosis?.overall || data.diagnosis || {};
        const diagResult = diag.diagnosis || 'unknown';

        dashBadge.textContent = diagResult;
        dashBadge.className = 'badge ' + (diagResult === 'positive' ? 'positive' : 'negative');

        const chain = diag.reasoning_chain || data.reasoning_trace?.reasoning_chain || [];

        renderDiagnosis(diag);
        renderReasoningChain(chain);
        renderConcepts(data.concepts || {});
        renderStats(data.pipeline_trace);
        renderGraph(data.pipeline_trace);
        renderFindingsGraph(diag, chain, data.concepts || {});
    }

    // ── Diagnosis Card ───────────────────────────────────────────

    function renderDiagnosis(diag) {
        const body = $('#diagnosis-body');
        if (!diag || !diag.diagnosis) {
            body.innerHTML = '<p class="placeholder-text">No diagnosis data.</p>';
            return;
        }

        const confidence = diag.confidence || 0;
        const pct = Math.round(confidence * 100);
        const circumference = 2 * Math.PI * 36;
        const offset = circumference - (confidence * circumference);

        const gaugeColor = confidence >= 0.7
            ? 'url(#gaugeGrad)'
            : confidence >= 0.4 ? '#ffab40' : '#ff5274';

        let html = `
            <div class="diag-verdict">
                <div class="confidence-gauge">
                    <svg viewBox="0 0 80 80">
                        <defs>
                            <linearGradient id="gaugeGrad" x1="0" y1="0" x2="80" y2="80" gradientUnits="userSpaceOnUse">
                                <stop stop-color="#00e5ff" />
                                <stop offset="1" stop-color="#00e676" />
                            </linearGradient>
                        </defs>
                        <circle class="gauge-bg" cx="40" cy="40" r="36" />
                        <circle class="gauge-fill" cx="40" cy="40" r="36"
                                stroke="${gaugeColor}"
                                stroke-dasharray="${circumference}"
                                stroke-dashoffset="${offset}" />
                    </svg>
                    <div class="gauge-label">
                        <span class="gauge-value">${pct}%</span>
                        <span class="gauge-text">confidence</span>
                    </div>
                </div>
                <div class="verdict-text">
                    <h4>${diag.diagnosis === 'positive' ? '⚠ Positive' : '✓ Negative'}</h4>
                    <p>${diag.notes || ''}</p>
                </div>
            </div>
        `;

        // Evidence
        if (diag.evidence && diag.evidence.length) {
            html += '<div class="evidence-section"><h5>Key Evidence</h5>';
            for (const ev of diag.evidence) {
                html += `<div class="evidence-item"><span class="evidence-bullet">›</span><span>${ev}</span></div>`;
            }
            html += '</div>';
        }

        // Weights
        if (diag.weights && diag.weights.length) {
            html += '<div class="weights-grid">';
            for (const w of diag.weights) {
                html += `<span class="weight-tag">${w.indicator_name} <span class="weight-value">${(w.weight * 100).toFixed(0)}%</span></span>`;
            }
            html += '</div>';
        }

        body.innerHTML = html;

        // Animate gauge
        requestAnimationFrame(() => {
            const fill = body.querySelector('.gauge-fill');
            if (fill) {
                fill.style.strokeDashoffset = circumference;
                requestAnimationFrame(() => { fill.style.strokeDashoffset = offset; });
            }
        });
    }

    // ── Reasoning Chain ──────────────────────────────────────────

    function renderReasoningChain(chain) {
        const list = $('#reasoning-list');
        if (!chain || !chain.length) {
            list.innerHTML = '<p class="placeholder-text">No reasoning chain available.</p>';
            return;
        }

        list.innerHTML = '';
        for (const step of chain) {
            const supports = step.supports_diagnosis !== false;
            const contrib = step.confidence_contribution || 0;
            const barW = Math.min(Math.abs(contrib) * 500, 100);

            const card = document.createElement('div');
            card.className = 'reasoning-step' + (supports ? '' : ' opposes');
            card.innerHTML = `
                <div class="step-header">
                    <span class="step-observation">${step.observation || '—'}</span>
                    <span class="step-contribution ${supports ? '' : 'negative-contrib'}">
                        ${supports ? '+' : '−'}${(contrib * 100).toFixed(0)}%
                    </span>
                </div>
                <div class="step-significance">${step.clinical_significance || ''}</div>
                <div class="step-bar">
                    <div class="step-bar-fill ${supports ? '' : 'negative-bar'}" style="width: 0%"></div>
                </div>
            `;
            list.appendChild(card);

            // Animate bar
            requestAnimationFrame(() => {
                const bar = card.querySelector('.step-bar-fill');
                if (bar) bar.style.width = barW + '%';
            });
        }
    }

    // ── Medical Concepts ─────────────────────────────────────────

    function renderConcepts(conceptsData) {
        const container = $('#concepts-list');
        if (!conceptsData || !Object.keys(conceptsData).length) {
            container.innerHTML = '<p class="placeholder-text">No concepts extracted.</p>';
            return;
        }

        // Flatten all concepts across steps, deduplicate by name
        const seen = new Set();
        const allConcepts = [];
        for (const stepConcepts of Object.values(conceptsData)) {
            if (!Array.isArray(stepConcepts)) continue;
            for (const c of stepConcepts) {
                const key = c.name.toLowerCase();
                if (!seen.has(key)) {
                    seen.add(key);
                    allConcepts.push(c);
                }
            }
        }

        if (!allConcepts.length) {
            container.innerHTML = '<p class="placeholder-text">No concepts extracted.</p>';
            return;
        }

        // Group by category
        const groups = {};
        for (const c of allConcepts) {
            const cat = (c.category || 'finding').toLowerCase();
            if (!groups[cat]) groups[cat] = [];
            groups[cat].push(c);
        }

        const categoryOrder = ['condition', 'finding', 'symptom', 'anatomy', 'measurement'];
        container.innerHTML = '';

        for (const cat of categoryOrder) {
            const items = groups[cat];
            if (!items || !items.length) continue;

            const section = document.createElement('div');
            section.className = 'concept-category';
            section.innerHTML = `<h4><span class="category-dot ${cat}"></span>${cat}s (${items.length})</h4>`;

            const tags = document.createElement('div');
            for (const c of items) {
                const tag = document.createElement('span');
                tag.className = 'concept-tag ' + cat;
                tag.textContent = c.name;
                tag.title = c.relevance || c.original_text || '';
                tags.appendChild(tag);
            }
            section.appendChild(tags);
            container.appendChild(section);
        }
    }

    // ── Pipeline Stats ───────────────────────────────────────────

    function renderStats(trace) {
        const grid = $('#stats-grid');
        if (!trace) {
            grid.innerHTML = '<p class="placeholder-text" style="grid-column:1/-1;">No trace data.</p>';
            return;
        }

        const nodes = trace.nodes || [];
        const totalDur = trace.total_duration_seconds || 0;
        const completedCount = nodes.filter(n => n.status === 'completed').length;
        const errorCount = nodes.filter(n => n.status === 'error').length;

        grid.innerHTML = `
            <div class="stat-card">
                <span class="stat-label">Total Time</span>
                <span class="stat-value">${totalDur.toFixed(1)}s</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Nodes</span>
                <span class="stat-value">${nodes.length}</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Completed</span>
                <span class="stat-value" style="color: var(--accent-emerald);">${completedCount}</span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Errors</span>
                <span class="stat-value" style="color: ${errorCount ? 'var(--accent-rose)' : 'var(--accent-emerald)'};">${errorCount}</span>
            </div>
        `;
    }

    // ── Pipeline Graph ───────────────────────────────────────────

    function renderGraph(trace) {
        if (!pipelineGraph) {
            pipelineGraph = new PipelineGraph('pipeline-canvas');
        }
        if (trace) {
            pipelineGraph.setTrace(trace);
        }
    }

    // ── Findings Knowledge Graph ─────────────────────────────────

    function renderFindingsGraph(diagnosis, reasoningChain, concepts) {
        if (!findingsGraph) {
            findingsGraph = new FindingsGraph('findings-canvas');
        }
        if (findingsGraph) {
            findingsGraph.setData({ diagnosis, reasoningChain, concepts });
        }
    }

    // ── Init ─────────────────────────────────────────────────────

    loadDiseases();
})();
