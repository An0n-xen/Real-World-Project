class PipelineGraph {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.nodes = [];
        this.edges = [];
        this.hoveredNode = null;
        this.dpr = typeof window !== "undefined" ? (window.devicePixelRatio || 1) : 1;

        this._onMouseMove = this._onMouseMove.bind(this);
        this._onMouseLeave = this._onMouseLeave.bind(this);
        this.canvas.addEventListener('mousemove', this._onMouseMove);
        this.canvas.addEventListener('mouseleave', this._onMouseLeave);
    }

    static STATUS_COLORS = {
        completed: { bg: 'rgba(37, 99, 235, 0.07)', border: '#2563EB', text: '#1D4ED8', glow: 'rgba(37, 99, 235, 0.15)' },
        running:   { bg: 'rgba(37, 99, 235, 0.07)', border: '#2563EB', text: '#1D4ED8', glow: 'rgba(37, 99, 235, 0.15)' },
        error:     { bg: 'rgba(225, 29, 72, 0.07)', border: '#E11D48', text: '#BE123C', glow: 'rgba(225, 29, 72, 0.15)' },
        pending:   { bg: 'rgba(0, 0, 0, 0.02)', border: '#CBD5E1', text: '#64748B', glow: 'rgba(0,0,0,0.03)' },
    };

    static NODE_LABELS = {
        load_config:          'Load Config',
        retrieve_guidelines:  'Retrieve Guidelines',
        generate_plan:        'Generate Plan',
        generate_tools:       'Generate Tools',
        execute_steps:        'Execute Steps',
        collect_indicators:   'Collect Indicators',
        final_decision:       'Final Decision',
    };

    setTrace(traceData) {
        if (!traceData || !traceData.nodes) return;

        const nodeOrder = [
            'load_config', 'retrieve_guidelines', 'generate_plan',
            'generate_tools', 'execute_steps', 'collect_indicators', 'final_decision',
        ];

        const traceMap = {};
        for (const n of traceData.nodes) traceMap[n.node_name] = n;

        const padding = 20;
        const nodeW = 260;
        const nodeH = 50;
        const gapY = 18;

        this.nodes = nodeOrder.map((name, i) => {
            const trace = traceMap[name] || { status: 'pending', duration_seconds: 0 };
            return {
                id: name,
                label: PipelineGraph.NODE_LABELS[name] || name,
                status: trace.status || 'pending',
                duration: trace.duration_seconds || 0,
                inputs: trace.inputs_summary || {},
                outputs: trace.outputs_summary || {},
                x: 0,
                y: padding + i * (nodeH + gapY),
                w: nodeW,
                h: nodeH,
            };
        });

        this._setupCanvas();

        const cw = this.canvas.width / this.dpr;
        const startX = (cw - nodeW) / 2;
        for (const node of this.nodes) node.x = startX;

        this.edges = [];
        for (let i = 0; i < this.nodes.length - 1; i++) this.edges.push({ from: i, to: i + 1 });

        for (const edge of this.edges) this._drawEdge(this.nodes[edge.from], this.nodes[edge.to]);
        for (const node of this.nodes) this._drawNode(node, false);
    }

    render() {
        this._setupCanvas();
        for (const edge of this.edges) this._drawEdge(this.nodes[edge.from], this.nodes[edge.to]);
        for (const node of this.nodes) this._drawNode(node, node === this.hoveredNode);
    }

    _setupCanvas() {
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * this.dpr;
        const contentH = this.nodes.length > 0
            ? this.nodes[this.nodes.length - 1].y + this.nodes[this.nodes.length - 1].h + 20
            : 500;
        this.canvas.height = contentH * this.dpr;
        this.canvas.style.height = contentH + 'px';
        this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    }

    _drawEdge(from, to) {
        const ctx = this.ctx;
        const x = from.x + from.w / 2;
        const y1 = from.y + from.h;
        const y2 = to.y;
        const cy = (y1 + y2) / 2;

        ctx.save();
        ctx.beginPath();
        ctx.moveTo(x, y1);
        ctx.bezierCurveTo(x, cy, x, cy, x, y2);

        const grad = ctx.createLinearGradient(x, y1, x, y2);
        const fc = PipelineGraph.STATUS_COLORS[from.status] || PipelineGraph.STATUS_COLORS.pending;
        const tc = PipelineGraph.STATUS_COLORS[to.status] || PipelineGraph.STATUS_COLORS.pending;
        grad.addColorStop(0, fc.border);
        grad.addColorStop(1, tc.border);
        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.5;
        ctx.globalAlpha = 0.4;
        ctx.stroke();

        const sz = 4;
        ctx.globalAlpha = 0.6;
        ctx.fillStyle = tc.border;
        ctx.beginPath();
        ctx.moveTo(x, y2);
        ctx.lineTo(x - sz, y2 - sz * 1.4);
        ctx.lineTo(x + sz, y2 - sz * 1.4);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    }

    _drawNode(node, hovered) {
        const ctx = this.ctx;
        const colors = PipelineGraph.STATUS_COLORS[node.status] || PipelineGraph.STATUS_COLORS.pending;
        const { x, y, w, h } = node;

        ctx.save();
        if (hovered) { ctx.shadowColor = colors.glow; ctx.shadowBlur = 14; }

        ctx.fillStyle = hovered ? '#0B1426' : colors.bg;
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, 8);
        ctx.fill();

        ctx.strokeStyle = hovered ? 'rgba(37, 99, 235, 0.4)' : colors.border;
        ctx.lineWidth = hovered ? 1.5 : 1;
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Status dot
        ctx.fillStyle = colors.border;
        ctx.beginPath();
        ctx.arc(x + 16, y + h / 2, 4, 0, Math.PI * 2);
        ctx.fill();

        // Label
        ctx.fillStyle = hovered ? '#E2E8F0' : '#1A1F36';
        ctx.font = '600 13px var(--font-sans, sans-serif)';
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'left';
        ctx.fillText(node.label, x + 30, y + h / 2 - 7);

        // Duration
        ctx.fillStyle = hovered ? 'rgba(226, 232, 240, 0.6)' : '#8792A2';
        ctx.font = '500 11px var(--font-mono, monospace)';
        const dur = node.duration >= 1 ? `${node.duration.toFixed(1)}s` : `${(node.duration * 1000).toFixed(0)}ms`;
        ctx.fillText(dur, x + 30, y + h / 2 + 9);

        // Status badge
        ctx.fillStyle = hovered ? 'rgba(96, 165, 250, 0.7)' : colors.text;
        ctx.globalAlpha = hovered ? 1 : 0.8;
        ctx.font = '700 10px var(--font-sans, sans-serif)';
        ctx.textAlign = 'right';
        ctx.fillText(node.status.toUpperCase(), x + w - 12, y + h / 2);
        ctx.textAlign = 'left';
        ctx.globalAlpha = 1;

        ctx.restore();
    }

    _getNodeAt(px, py) {
        for (const node of this.nodes) {
            if (px >= node.x && px <= node.x + node.w && py >= node.y && py <= node.y + node.h) return node;
        }
        return null;
    }

    _onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const node = this._getNodeAt(e.clientX - rect.left, e.clientY - rect.top);
        if (node !== this.hoveredNode) {
            this.hoveredNode = node;
            this.render();
            const tooltip = document.getElementById('node-tooltip');
            if (node) {
                this.canvas.style.cursor = 'pointer';
                this._showTooltip(e, node);
            } else {
                this.canvas.style.cursor = 'default';
                tooltip.style.display = 'none';
            }
        } else if (node) {
            this._moveTooltip(e);
        }
    }

    _onMouseLeave() {
        if (this.hoveredNode) {
            this.hoveredNode = null;
            this.render();
            this.canvas.style.cursor = 'default';
            document.getElementById('node-tooltip').style.display = 'none';
        }
    }

    _showTooltip(e, node) {
        const tooltip = document.getElementById('node-tooltip');
        if (!tooltip) return;
        const headerEl = document.getElementById('tooltip-header');
        const bodyEl = document.getElementById('tooltip-body');
        if (headerEl) headerEl.textContent = node.label + ' — ' + node.status;
        let html = `<div class="tooltip-row"><span class="tooltip-label">Duration:</span><span>${node.duration.toFixed(3)}s</span></div>`;
        const keys = ['disease_name', 'image_path', 'save_dir', 'rag_context'];
        for (const k of keys) {
            if (node.inputs[k]) {
                let v = String(node.inputs[k]);
                if (v.length > 55) v = v.slice(0, 52) + '…';
                html += `<div class="tooltip-row"><span class="tooltip-label">${k}:</span><span>${v}</span></div>`;
            }
        }
        if (bodyEl) bodyEl.innerHTML = html;
        tooltip.style.display = 'block';
        this._moveTooltip(e);
    }

    _moveTooltip(e) {
        const t = document.getElementById('node-tooltip');
        let tx = e.clientX + 14, ty = e.clientY + 14;
        if (typeof window !== "undefined") {
            if (tx + t.offsetWidth > window.innerWidth - 10) tx = e.clientX - t.offsetWidth - 10;
            if (ty + t.offsetHeight > window.innerHeight - 10) ty = e.clientY - t.offsetHeight - 10;
        }
        t.style.left = tx + 'px';
        t.style.top = ty + 'px';
    }
}


/* ═══════════════════════════════════════════════════════════════════
   Findings Knowledge Graph — Force-Directed with Physics
   ═══════════════════════════════════════════════════════════════════ */

class FindingsGraph {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.dpr = typeof window !== "undefined" ? (window.devicePixelRatio || 1) : 1;
        this.graphNodes = [];
        this.graphEdges = [];
        this.hoveredNode = null;
        this.dragNode = null;
        this.running = false;

        // Physics tunables
        this.REPULSION = 6000;
        this.ATTRACTION = 0.002;
        this.CENTER_GRAVITY = 0.003;
        this.DAMPING = 0.88;
        this.COLLISION_PAD = 15;
        this.MAX_SPEED = 8;

        this._mouseX = 0;
        this._mouseY = 0;

        this._onMouseDown = this._onMouseDown.bind(this);
        this._onMouseMove = this._onMouseMove.bind(this);
        this._onMouseUp   = this._onMouseUp.bind(this);
        this._onMouseLeave = this._onMouseLeave.bind(this);

        this.canvas.addEventListener('mousedown', this._onMouseDown);
        this.canvas.addEventListener('mousemove', this._onMouseMove);
        this.canvas.addEventListener('mouseup', this._onMouseUp);
        this.canvas.addEventListener('mouseleave', this._onMouseLeave);

        this.canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const t = e.touches[0];
            this._onMouseDown({ clientX: t.clientX, clientY: t.clientY });
        }, { passive: false });
        this.canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            const t = e.touches[0];
            this._onMouseMove({ clientX: t.clientX, clientY: t.clientY });
        }, { passive: false });
        this.canvas.addEventListener('touchend', () => this._onMouseUp({}));
    }

    static CATEGORY_COLORS = {
        diagnosis:   { fill: '#059669', border: '#10B981', bg: 'rgba(16, 185, 129, 0.12)' },
        evidence:    { fill: '#0284C7', border: '#0EA5E9', bg: 'rgba(14, 165, 233, 0.10)' },
        finding:     { fill: '#2563EB', border: '#3B82F6', bg: 'rgba(37, 99, 235, 0.08)' },
        condition:   { fill: '#E11D48', border: '#F43F5E', bg: 'rgba(244, 63, 94, 0.08)' },
        symptom:     { fill: '#D97706', border: '#F59E0B', bg: 'rgba(245, 158, 11, 0.08)' },
        anatomy:     { fill: '#7C3AED', border: '#8B5CF6', bg: 'rgba(139, 92, 246, 0.08)' },
        measurement: { fill: '#059669', border: '#10B981', bg: 'rgba(16, 185, 129, 0.08)' },
    };

    setData({ diagnosis, reasoningChain, concepts }) {
        this.graphNodes = [];
        this.graphEdges = [];
        if (!diagnosis && (!reasoningChain || !reasoningChain.length)) return;

        this._setupCanvas();
        const cw = this.canvas.width / this.dpr;
        const ch = this.canvas.height / this.dpr;
        const cx = cw / 2;
        const cy = ch / 2;

        const diagLabel = diagnosis
            ? `${(diagnosis.diagnosis || 'Unknown').toUpperCase()} (${Math.round((diagnosis.confidence || 0) * 100)}%)`
            : 'DIAGNOSIS';

        this.graphNodes.push({
            id: 'diagnosis',
            label: diagLabel,
            shortLabel: (diagnosis?.diagnosis || 'Diagnosis').toUpperCase(),
            type: 'diagnosis',
            x: cx, y: cy,
            vx: 0, vy: 0,
            r: 52,
            fixed: true,
            detail: diagnosis?.notes || '',
            contribution: diagnosis?.confidence || 0,
        });

        const chain = reasoningChain || [];
        const ring1R = Math.min(cw, ch) * 0.35;

        chain.forEach((step, i) => {
            const angle = (i / chain.length) * Math.PI * 2 - Math.PI / 2;
            const jitter = (Math.random() - 0.5) * 30;
            const nodeId = `obs_${i}`;

            this.graphNodes.push({
                id: nodeId,
                label: step.observation || `Observation ${i + 1}`,
                shortLabel: step.observation || `Observation ${i + 1}`,
                type: step.supports_diagnosis !== false ? 'evidence' : 'symptom',
                x: cx + Math.cos(angle) * ring1R + jitter,
                y: cy + Math.sin(angle) * ring1R + jitter,
                vx: (Math.random() - 0.5) * 2,
                vy: (Math.random() - 0.5) * 2,
                r: 36,
                fixed: false,
                detail: step.clinical_significance || '',
                contribution: step.confidence_contribution || 0,
                supports: step.supports_diagnosis !== false,
            });

            this.graphEdges.push({
                from: nodeId, to: 'diagnosis',
                weight: step.confidence_contribution || 0.05,
                supports: step.supports_diagnosis !== false,
                restLength: ring1R * 1.1,
            });
        });

        if (concepts && typeof concepts === 'object') {
            const seen = new Set();
            const allConcepts = [];
            for (const arr of Object.values(concepts)) {
                if (!Array.isArray(arr)) continue;
                for (const c of arr) {
                    const key = c.name.toLowerCase();
                    if (!seen.has(key)) { seen.add(key); allConcepts.push(c); }
                }
            }

            const topConcepts = allConcepts.slice(0, 18);
            const ring2R = Math.min(cw, ch) * 0.48;

            topConcepts.forEach((c, i) => {
                const angle = (i / topConcepts.length) * Math.PI * 2 - Math.PI / 2;
                const jitter = (Math.random() - 0.5) * 40;
                const cat = (c.category || 'finding').toLowerCase();
                const nodeId = `concept_${i}`;

                this.graphNodes.push({
                    id: nodeId,
                    label: c.name,
                    shortLabel: c.name,
                    type: cat,
                    x: cx + Math.cos(angle) * ring2R + jitter,
                    y: cy + Math.sin(angle) * ring2R + jitter,
                    vx: (Math.random() - 0.5) * 1.5,
                    vy: (Math.random() - 0.5) * 1.5,
                    r: 26,
                    fixed: false,
                    detail: c.relevance || c.original_text || '',
                    contribution: 0,
                });

                let bestObs = null, bestScore = 0;
                const nameLow = c.name.toLowerCase();
                for (let j = 0; j < chain.length; j++) {
                    const obsText = ((chain[j].observation || '') + ' ' + (chain[j].clinical_significance || '')).toLowerCase();
                    let score = 0;
                    if (obsText.includes(nameLow)) score += 3;
                    for (const w of nameLow.split(/\s+/)) {
                        if (w.length > 3 && obsText.includes(w)) score += 1;
                    }
                    if (score > bestScore) { bestScore = score; bestObs = `obs_${j}`; }
                }

                this.graphEdges.push({
                    from: nodeId,
                    to: (bestObs && bestScore >= 1) ? bestObs : 'diagnosis',
                    weight: 0.03,
                    supports: true,
                    secondary: true,
                    restLength: (bestObs && bestScore >= 1) ? ring2R * 0.7 : ring2R * 1.25,
                });
            });
        }

        for (let i = 0; i < chain.length; i++) {
            for (let j = i + 1; j < chain.length; j++) {
                const wordsI = new Set((chain[i].observation || '').toLowerCase().split(/\s+/).filter(w => w.length > 4));
                const wordsJ = (chain[j].observation || '').toLowerCase().split(/\s+/).filter(w => w.length > 4);
                let shared = 0;
                for (const w of wordsJ) { if (wordsI.has(w)) shared++; }
                if (shared >= 1) {
                    this.graphEdges.push({
                        from: `obs_${i}`, to: `obs_${j}`,
                        weight: 0.02, supports: true,
                        crossLink: true, restLength: ring1R * 0.9,
                    });
                }
            }
        }

        if (!this.running) {
            this.running = true;
            this._tick();
        }
    }

    _tick() {
        if (!this.running) return;
        this._simulate();
        this._render();
        if (typeof window !== "undefined") {
            requestAnimationFrame(() => this._tick());
        }
    }

    _simulate() {
        const nodes = this.graphNodes;
        const edges = this.graphEdges;
        const cw = this.canvas.width / this.dpr;
        const ch = this.canvas.height / this.dpr;
        const cx = cw / 2;
        const cy = ch / 2;

        for (const n of nodes) { n.fx = 0; n.fy = 0; }

        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const a = nodes[i], b = nodes[j];
                let dx = b.x - a.x;
                let dy = b.y - a.y;
                let dist = Math.sqrt(dx * dx + dy * dy) || 1;

                const force = this.REPULSION / (dist * dist);
                const fx = (dx / dist) * force;
                const fy = (dy / dist) * force;

                a.fx -= fx; a.fy -= fy;
                b.fx += fx; b.fy += fy;
            }
        }

        for (const edge of edges) {
            const a = this._getById(edge.from);
            const b = this._getById(edge.to);
            if (!a || !b) continue;

            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const rest = edge.restLength || 150;
            const displacement = dist - rest;
            const k = edge.secondary ? this.ATTRACTION * 0.5 : this.ATTRACTION;
            const force = k * displacement;

            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            a.fx += fx; a.fy += fy;
            b.fx -= fx; b.fy -= fy;
        }

        for (const n of nodes) {
            if (n.fixed) continue;
            n.fx += (cx - n.x) * this.CENTER_GRAVITY;
            n.fy += (cy - n.y) * this.CENTER_GRAVITY;
        }

        for (const n of nodes) {
            if (n.fixed) continue;
            if (n === this.dragNode) continue;

            n.vx = (n.vx + n.fx) * this.DAMPING;
            n.vy = (n.vy + n.fy) * this.DAMPING;

            const speed = Math.sqrt(n.vx * n.vx + n.vy * n.vy);
            if (speed > this.MAX_SPEED) {
                n.vx = (n.vx / speed) * this.MAX_SPEED;
                n.vy = (n.vy / speed) * this.MAX_SPEED;
            }

            n.x += n.vx;
            n.y += n.vy;

            n.x = Math.max(n.r + 4, Math.min(cw - n.r - 4, n.x));
            n.y = Math.max(n.r + 4, Math.min(ch - n.r - 4, n.y));
        }

        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const a = nodes[i], b = nodes[j];
                const dx = b.x - a.x;
                const dy = b.y - a.y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                const minDist = a.r + b.r + this.COLLISION_PAD;

                if (dist < minDist) {
                    const overlap = (minDist - dist) / 2;
                    const nx = dx / dist;
                    const ny = dy / dist;

                    if (!a.fixed && a !== this.dragNode) {
                        a.x -= nx * overlap;
                        a.y -= ny * overlap;
                    }
                    if (!b.fixed && b !== this.dragNode) {
                        b.x += nx * overlap;
                        b.y += ny * overlap;
                    }
                }
            }
        }
    }

    _getById(id) {
        return this.graphNodes.find(n => n.id === id);
    }

    _setupCanvas() {
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * this.dpr;
        this.canvas.height = rect.height * this.dpr;
        this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    }

    _render() {
        this._setupCanvas();
        const ctx = this.ctx;

        for (const edge of this.graphEdges) this._drawEdge(edge);
        for (const node of this.graphNodes) this._drawNode(node, node === this.hoveredNode, node === this.dragNode);
    }

    _drawEdge(edge) {
        const from = this._getById(edge.from);
        const to = this._getById(edge.to);
        if (!from || !to) return;

        const ctx = this.ctx;
        ctx.save();

        const isHighlighted = this.hoveredNode && (this.hoveredNode.id === edge.from || this.hoveredNode.id === edge.to);
        const alpha = isHighlighted ? 0.9 : (edge.crossLink ? 0.25 : edge.secondary ? 0.35 : 0.6);

        let baseLineW = edge.secondary ? 1 : Math.max(1.5, edge.weight * 8);
        const lineWidth = isHighlighted ? baseLineW + 1 : baseLineW;

        ctx.globalAlpha = alpha;
        ctx.lineWidth = lineWidth;

        if (edge.supports === false) {
            ctx.strokeStyle = '#E11D48';
        } else if (edge.crossLink) {
            ctx.strokeStyle = '#94A3B8';
            ctx.setLineDash([3, 4]);
        } else if (edge.secondary) {
            ctx.strokeStyle = '#CBD5E1';
        } else {
            const grad = ctx.createLinearGradient(from.x, from.y, to.x, to.y);
            grad.addColorStop(0, FindingsGraph.CATEGORY_COLORS[from.type]?.fill || '#0EA5E9');
            grad.addColorStop(1, FindingsGraph.CATEGORY_COLORS[to.type]?.fill || '#10B981');
            ctx.strokeStyle = grad;
        }

        ctx.beginPath();
        ctx.moveTo(from.x, from.y);

        if (edge.crossLink || edge.secondary) {
            ctx.lineTo(to.x, to.y);
        } else {
            const mx = (from.x + to.x) / 2;
            const my = (from.y + to.y) / 2;
            const dx = to.x - from.x;
            const dy = to.y - from.y;
            ctx.quadraticCurveTo(mx + dy * 0.04, my - dx * 0.04, to.x, to.y);
        }
        ctx.stroke();

        if (!edge.secondary && !edge.crossLink) {
            const angle = Math.atan2(to.y - from.y, to.x - from.x);
            const ad = to.r + 5;
            const ax = to.x - Math.cos(angle) * ad;
            const ay = to.y - Math.sin(angle) * ad;
            ctx.globalAlpha = alpha + 0.15;
            ctx.fillStyle = ctx.strokeStyle;
            ctx.beginPath();
            ctx.moveTo(ax, ay);
            ctx.lineTo(ax - Math.cos(angle - 0.45) * 7, ay - Math.sin(angle - 0.45) * 7);
            ctx.lineTo(ax - Math.cos(angle + 0.45) * 7, ay - Math.sin(angle + 0.45) * 7);
            ctx.closePath();
            ctx.fill();
        }

        ctx.restore();
    }

    _drawNode(node, hovered, dragged) {
        const ctx = this.ctx;
        const colors = FindingsGraph.CATEGORY_COLORS[node.type] || FindingsGraph.CATEGORY_COLORS.finding;
        const { x, y, r } = node;
        const active = hovered || dragged;

        ctx.save();

        if (active) {
            ctx.shadowColor = 'rgba(0, 0, 0, 0.08)';
            ctx.shadowBlur = 8;
        }

        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);

        if (node.type === 'diagnosis') {
            ctx.fillStyle = active ? colors.bg.replace(/[\d.]+\)$/, '0.25)') : colors.bg;
            ctx.fill();
            ctx.strokeStyle = colors.border;
            ctx.lineWidth = active ? 2.5 : 2;
            ctx.stroke();
        } else {
            ctx.fillStyle = '#FFFFFF';
            ctx.fill();
            ctx.strokeStyle = active ? colors.border : 'rgba(0,0,0,0.07)';
            ctx.lineWidth = active ? 1.5 : 1;
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(x, y, r - 2, 0, Math.PI * 2);
            ctx.strokeStyle = colors.bg.replace(/[\d.]+\)$/, '0.35)');
            ctx.lineWidth = 1;
            ctx.stroke();
        }
        ctx.shadowBlur = 0;

        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        if (node.type === 'diagnosis') {
            ctx.fillStyle = '#1A1F36';
            ctx.font = '800 13px var(--font-sans, sans-serif)';
            ctx.fillText(node.shortLabel, x, y - 7);

            ctx.font = '700 11px var(--font-mono, monospace)';
            ctx.fillStyle = colors.border;
            ctx.fillText(Math.round((node.contribution || 0) * 100) + '%', x, y + 10);
        } else {
            ctx.fillStyle = '#1A1F36';
            let fontSize = r >= 30 ? 10 : 9;
            ctx.font = `600 ${fontSize}px var(--font-sans, sans-serif)`;

            const lines = this._wrapText(node.shortLabel, r * 1.8);
            const lh = fontSize + 3;
            const sy = y - ((lines.length - 1) * lh) / 2;
            for (let i = 0; i < lines.length; i++) {
                ctx.fillText(lines[i], x, sy + i * lh);
            }
        }

        if (node.contribution > 0 && node.type !== 'diagnosis') {
            const arcAngle = Math.min(node.contribution * Math.PI * 8, Math.PI * 2);
            ctx.beginPath();
            ctx.arc(x, y, r + 4, -Math.PI / 2, -Math.PI / 2 + arcAngle);
            ctx.strokeStyle = node.supports === false ? '#E11D48' : colors.fill;
            ctx.lineWidth = 2.5;
            ctx.lineCap = 'round';
            ctx.stroke();
        }

        ctx.restore();
    }

    _wrapText(text, maxW) {
        if (!text) return [""];
        text = text.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase()).trim();

        const words = text.split(' ');
        const lines = [];
        let current = '';
        for (const w of words) {
            if (!w) continue;
            const test = current ? current + ' ' + w : w;
            if (test.length * 6 > maxW && current) {
                lines.push(current);
                current = w;
            } else {
                current = test;
            }
        }
        if (current) lines.push(current);

        if (lines.length > 3) {
            return [lines[0], lines[1], lines[2] + "…"];
        }
        return lines;
    }

    _truncate(text, max) {
        return text.length > max ? text.slice(0, max - 1) + '…' : text;
    }

    _getCanvasPos(e) {
        const rect = this.canvas.getBoundingClientRect();
        return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    _getNodeAt(px, py) {
        for (let i = this.graphNodes.length - 1; i >= 0; i--) {
            const n = this.graphNodes[i];
            const dx = px - n.x, dy = py - n.y;
            if (dx * dx + dy * dy <= (n.r + 4) * (n.r + 4)) return n;
        }
        return null;
    }

    _onMouseDown(e) {
        const pos = this._getCanvasPos(e);
        const node = this._getNodeAt(pos.x, pos.y);
        if (node && !node.fixed) {
            this.dragNode = node;
            this.dragNode.vx = 0;
            this.dragNode.vy = 0;
            this.canvas.style.cursor = 'grabbing';
        }
    }

    _onMouseMove(e) {
        const pos = this._getCanvasPos(e);
        this._mouseX = pos.x;
        this._mouseY = pos.y;

        if (this.dragNode) {
            this.dragNode.x = pos.x;
            this.dragNode.y = pos.y;
            this.dragNode.vx = 0;
            this.dragNode.vy = 0;
            this.canvas.style.cursor = 'grabbing';

            const t = document.getElementById('findings-tooltip');
            if (t) t.style.display = 'none';
            return;
        }

        const node = this._getNodeAt(pos.x, pos.y);
        if (node !== this.hoveredNode) {
            this.hoveredNode = node;
            const tooltip = document.getElementById('findings-tooltip');
            if (node) {
                this.canvas.style.cursor = 'grab';
                this._showTooltip(e, node, tooltip);
            } else {
                this.canvas.style.cursor = 'default';
                if (tooltip) tooltip.style.display = 'none';
            }
        } else if (node) {
            this._moveTooltip(e, document.getElementById('findings-tooltip'));
        }
    }

    _onMouseUp() {
        if (this.dragNode) {
            this.dragNode.vx = (Math.random() - 0.5) * 0.5;
            this.dragNode.vy = (Math.random() - 0.5) * 0.5;
            this.dragNode = null;
            this.canvas.style.cursor = this.hoveredNode ? 'grab' : 'default';
        }
    }

    _onMouseLeave() {
        this.dragNode = null;
        this.hoveredNode = null;
        this.canvas.style.cursor = 'default';
        const t = document.getElementById('findings-tooltip');
        if (t) t.style.display = 'none';
    }

    _showTooltip(e, node, tooltip) {
        if (!tooltip) return;
        const header = document.getElementById('findings-tooltip-header');
        const body = document.getElementById('findings-tooltip-body');

        if (header) header.textContent = node.label;
        let html = '';
        if (node.type !== 'diagnosis') {
            html += `<div class="tooltip-row"><span class="tooltip-label">Type:</span><span>${node.type}</span></div>`;
        }
        if (node.contribution > 0) {
            html += `<div class="tooltip-row"><span class="tooltip-label">Contribution:</span><span>${(node.contribution * 100).toFixed(0)}%</span></div>`;
        }
        if (node.supports !== undefined && node.type !== 'diagnosis') {
            html += `<div class="tooltip-row"><span class="tooltip-label">Supports:</span><span>${node.supports ? '✓ Yes' : '✗ No'}</span></div>`;
        }
        if (node.detail) {
            const det = node.detail.length > 120 ? node.detail.slice(0, 117) + '…' : node.detail;
            html += `<div style="margin-top:6px;opacity:0.55;font-size:0.68rem;line-height:1.4;">${det}</div>`;
        }
        if (body) body.innerHTML = html;
        tooltip.style.display = 'block';
        this._moveTooltip(e, tooltip);
    }

    _moveTooltip(e, tooltip) {
        if (!tooltip) return;
        let tx = e.clientX + 14, ty = e.clientY + 14;
        if (tx + tooltip.offsetWidth > innerWidth - 10) tx = e.clientX - tooltip.offsetWidth - 10;
        if (ty + tooltip.offsetHeight > innerHeight - 10) ty = e.clientY - tooltip.offsetHeight - 10;
        tooltip.style.left = tx + 'px';
        tooltip.style.top = ty + 'px';
    }

    destroy() {
        this.running = false;
    }
}


/* ── Exports ── */

window.PipelineGraph = PipelineGraph;
window.FindingsGraph = FindingsGraph;


export { PipelineGraph, FindingsGraph };
