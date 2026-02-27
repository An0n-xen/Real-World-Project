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
        completed: { bg: 'rgba(202, 255, 0, 0.15)', border: '#6DAE00', text: '#3A6000', glow: 'rgba(202, 255, 0, 0.3)' },
        running:   { bg: 'rgba(37, 99, 235, 0.1)', border: '#2563EB', text: '#1D4ED8', glow: 'rgba(37, 99, 235, 0.2)' },
        error:     { bg: 'rgba(244, 63, 94, 0.1)', border: '#F43F5E', text: '#E11D48', glow: 'rgba(244, 63, 94, 0.2)' },
        pending:   { bg: 'rgba(0, 0, 0, 0.03)', border: '#CBD5E1', text: '#64748B', glow: 'rgba(0,0,0,0.05)' },
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

        // Pre-build nodes with placeholder positions so _setupCanvas can measure height
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
                x: 0,          // will be corrected below after canvas resize
                y: padding + i * (nodeH + gapY),
                w: nodeW,
                h: nodeH,
            };
        });

        // Now resize the canvas to fit the nodes BEFORE computing X
        this._setupCanvas();

        // Recompute X using the actual rendered canvas width
        const cw = this.canvas.width / this.dpr;
        const startX = (cw - nodeW) / 2;
        for (const node of this.nodes) node.x = startX;

        this.edges = [];
        for (let i = 0; i < this.nodes.length - 1; i++) this.edges.push({ from: i, to: i + 1 });

        // Draw without calling _setupCanvas again (already done)
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
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.5;
        ctx.stroke();

        const sz = 5;
        ctx.globalAlpha = 0.7;
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
        if (hovered) { ctx.shadowColor = colors.glow; ctx.shadowBlur = 18; }

        ctx.fillStyle = hovered ? '#0D0E12' : colors.bg;
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, 8);
        ctx.fill();

        ctx.strokeStyle = hovered ? '#0D0E12' : colors.border;
        ctx.lineWidth = hovered ? 2 : 1.5;
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Status dot
        ctx.fillStyle = colors.border;
        ctx.beginPath();
        ctx.arc(x + 16, y + h / 2, 5, 0, Math.PI * 2);
        ctx.fill();

        // Label
        ctx.fillStyle = hovered ? '#CAFF00' : '#0D0E12';
        ctx.font = '600 13px var(--font-sans, sans-serif)';
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'left';
        ctx.fillText(node.label, x + 30, y + h / 2 - 7);

        // Duration
        ctx.fillStyle = hovered ? 'rgba(202, 255, 0, 0.7)' : '#64748B';
        ctx.font = '500 11px var(--font-mono, monospace)';
        const dur = node.duration >= 1 ? `${node.duration.toFixed(1)}s` : `${(node.duration * 1000).toFixed(0)}ms`;
        ctx.fillText(dur, x + 30, y + h / 2 + 9);

        // Status badge
        ctx.fillStyle = hovered ? 'rgba(202, 255, 0, 0.5)' : colors.text;
        ctx.globalAlpha = hovered ? 1 : 0.9;
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
   ═══════════════════════════════════════════════════════════════════
   Interactive floating-bubble graph:
     • Force simulation (repulsion, attraction, center gravity)
     • Collision detection (nodes push apart)
     • Mouse drag (grab, move, release)
     • Continuous animation loop
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
        this.REPULSION = 6000;      // stronger repulsion
        this.ATTRACTION = 0.002;    // weaker spring force (looser)
        this.CENTER_GRAVITY = 0.003;// very weak center pull
        this.DAMPING = 0.88;        // existing damping
        this.COLLISION_PAD = 15;    // more personal space
        this.MAX_SPEED = 8;         // existing speed cap

        // Mouse state
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

        // Touch support
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
        diagnosis:   { fill: '#059669', border: '#10B981', bg: 'rgba(16, 185, 129, 0.15)' },
        evidence:    { fill: '#0284C7', border: '#0EA5E9', bg: 'rgba(14, 165, 233, 0.12)' },
        finding:     { fill: '#0D9488', border: '#14B8A6', bg: 'rgba(20, 184, 166, 0.10)' },
        condition:   { fill: '#E11D48', border: '#F43F5E', bg: 'rgba(244, 63, 94, 0.10)' },
        symptom:     { fill: '#D97706', border: '#F59E0B', bg: 'rgba(245, 158, 11, 0.10)' },
        anatomy:     { fill: '#7C3AED', border: '#8B5CF6', bg: 'rgba(139, 92, 246, 0.10)' },
        measurement: { fill: '#059669', border: '#10B981', bg: 'rgba(16, 185, 129, 0.10)' },
    };

    // ── Data binding ──────────────────────────────────────────────

    setData({ diagnosis, reasoningChain, concepts }) {
        this.graphNodes = [];
        this.graphEdges = [];
        if (!diagnosis && (!reasoningChain || !reasoningChain.length)) return;

        this._setupCanvas();
        const cw = this.canvas.width / this.dpr;
        const ch = this.canvas.height / this.dpr;
        const cx = cw / 2;
        const cy = ch / 2;

        // 1. Central diagnosis node (fixed at center)
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
            r: 46,
            fixed: true,   // diagnosis stays in center
            detail: diagnosis?.notes || '',
            contribution: diagnosis?.confidence || 0,
        });

        // 2. Reasoning observations (Ring 1)
        const chain = reasoningChain || [];
        const ring1R = Math.min(cw, ch) * 0.35; // increased from 0.26

        chain.forEach((step, i) => {
            const angle = (i / chain.length) * Math.PI * 2 - Math.PI / 2;
            const jitter = (Math.random() - 0.5) * 30;
            const nodeId = `obs_${i}`;

            this.graphNodes.push({
                id: nodeId,
                label: step.observation || `Observation ${i + 1}`,
                shortLabel: this._truncate(step.observation || '', 24),
                type: step.supports_diagnosis !== false ? 'evidence' : 'symptom',
                x: cx + Math.cos(angle) * ring1R + jitter,
                y: cy + Math.sin(angle) * ring1R + jitter,
                vx: (Math.random() - 0.5) * 2,
                vy: (Math.random() - 0.5) * 2,
                r: 30,
                fixed: false,
                detail: step.clinical_significance || '',
                contribution: step.confidence_contribution || 0,
                supports: step.supports_diagnosis !== false,
            });

            this.graphEdges.push({
                from: nodeId, to: 'diagnosis',
                weight: step.confidence_contribution || 0.05,
                supports: step.supports_diagnosis !== false,
                restLength: ring1R * 1.1, // longer rest length
            });
        });

        // 3. Medical concepts (Ring 2)
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
            const ring2R = Math.min(cw, ch) * 0.48; // increased from 0.42

            topConcepts.forEach((c, i) => {
                const angle = (i / topConcepts.length) * Math.PI * 2 - Math.PI / 2;
                const jitter = (Math.random() - 0.5) * 40;
                const cat = (c.category || 'finding').toLowerCase();
                const nodeId = `concept_${i}`;

                this.graphNodes.push({
                    id: nodeId,
                    label: c.name,
                    shortLabel: this._truncate(c.name, 16),
                    type: cat,
                    x: cx + Math.cos(angle) * ring2R + jitter,
                    y: cy + Math.sin(angle) * ring2R + jitter,
                    vx: (Math.random() - 0.5) * 1.5,
                    vy: (Math.random() - 0.5) * 1.5,
                    r: 18,
                    fixed: false,
                    detail: c.relevance || c.original_text || '',
                    contribution: 0,
                });

                // Link to best matching observation
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
                    restLength: (bestObs && bestScore >= 1) ? ring2R * 0.7 : ring2R * 1.25, // increased spacing
                });
            });
        }

        // 4. Cross-links between related observations
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
                        crossLink: true, restLength: ring1R * 0.9, // looser cross links
                    });
                }
            }
        }

        // Start animation
        if (!this.running) {
            this.running = true;
            this._tick();
        }
    }

    // ── Physics loop ──────────────────────────────────────────────

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

        // Reset forces
        for (const n of nodes) { n.fx = 0; n.fy = 0; }

        // 1. Node-node repulsion (Coulomb)
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const a = nodes[i], b = nodes[j];
                let dx = b.x - a.x;
                let dy = b.y - a.y;
                let dist = Math.sqrt(dx * dx + dy * dy) || 1;
                const minDist = a.r + b.r + this.COLLISION_PAD;

                // Stronger repulsion when close
                const force = this.REPULSION / (dist * dist);
                const fx = (dx / dist) * force;
                const fy = (dy / dist) * force;

                a.fx -= fx; a.fy -= fy;
                b.fx += fx; b.fy += fy;
            }
        }

        // 2. Edge attraction (spring)
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

        // 3. Center gravity
        for (const n of nodes) {
            if (n.fixed) continue;
            n.fx += (cx - n.x) * this.CENTER_GRAVITY;
            n.fy += (cy - n.y) * this.CENTER_GRAVITY;
        }

        // 4. Integrate velocity → position
        for (const n of nodes) {
            if (n.fixed) continue;
            if (n === this.dragNode) continue; // dragged node follows mouse

            n.vx = (n.vx + n.fx) * this.DAMPING;
            n.vy = (n.vy + n.fy) * this.DAMPING;

            // Speed cap
            const speed = Math.sqrt(n.vx * n.vx + n.vy * n.vy);
            if (speed > this.MAX_SPEED) {
                n.vx = (n.vx / speed) * this.MAX_SPEED;
                n.vy = (n.vy / speed) * this.MAX_SPEED;
            }

            n.x += n.vx;
            n.y += n.vy;

            // Boundary containment
            n.x = Math.max(n.r + 4, Math.min(cw - n.r - 4, n.x));
            n.y = Math.max(n.r + 4, Math.min(ch - n.r - 4, n.y));
        }

        // 5. Hard collision resolution (overlapping bubbles push apart)
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

    // ── Rendering ─────────────────────────────────────────────────

    _setupCanvas() {
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * this.dpr;
        this.canvas.height = rect.height * this.dpr;
        this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    }

    _render() {
        this._setupCanvas();
        const ctx = this.ctx;

        // Edges
        for (const edge of this.graphEdges) this._drawEdge(edge);

        // Nodes
        for (const node of this.graphNodes) this._drawNode(node, node === this.hoveredNode, node === this.dragNode);
    }

    _drawEdge(edge) {
        const from = this._getById(edge.from);
        const to = this._getById(edge.to);
        if (!from || !to) return;

        const ctx = this.ctx;
        ctx.save();

        const lineWidth = edge.secondary ? 1 : Math.max(1.5, edge.weight * 15);
        const isHighlighted = this.hoveredNode && (this.hoveredNode.id === edge.from || this.hoveredNode.id === edge.to);
        const alpha = isHighlighted ? 0.6 : (edge.crossLink ? 0.12 : edge.secondary ? 0.15 : 0.3);

        ctx.globalAlpha = alpha;
        ctx.lineWidth = isHighlighted ? lineWidth + 0.5 : lineWidth;

        if (edge.supports === false) {
            ctx.strokeStyle = '#ff5274';
        } else if (edge.crossLink) {
            ctx.strokeStyle = '#5a6785';
            ctx.setLineDash([4, 4]);
        } else if (edge.secondary) {
            ctx.strokeStyle = '#3a4a6a';
        } else {
            const grad = ctx.createLinearGradient(from.x, from.y, to.x, to.y);
            grad.addColorStop(0, FindingsGraph.CATEGORY_COLORS[from.type]?.fill || '#00e5ff');
            grad.addColorStop(1, FindingsGraph.CATEGORY_COLORS[to.type]?.fill || '#00e676');
            ctx.strokeStyle = grad;
        }

        // Curved line
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        const mx = (from.x + to.x) / 2;
        const my = (from.y + to.y) / 2;
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const curveOff = edge.crossLink ? 25 : 0;
        ctx.quadraticCurveTo(mx + dy * 0.08 + curveOff, my - dx * 0.08 + curveOff, to.x, to.y);
        ctx.stroke();

        // Arrows on primary edges
        if (!edge.secondary && !edge.crossLink) {
            const angle = Math.atan2(to.y - from.y, to.x - from.x);
            const ad = to.r + 5;
            const ax = to.x - Math.cos(angle) * ad;
            const ay = to.y - Math.sin(angle) * ad;
            ctx.globalAlpha = alpha + 0.15;
            ctx.fillStyle = ctx.strokeStyle;
            ctx.beginPath();
            ctx.moveTo(ax + Math.cos(angle) * 7, ay + Math.sin(angle) * 7);
            ctx.lineTo(ax + Math.cos(angle + 2.5) * 5, ay + Math.sin(angle + 2.5) * 5);
            ctx.lineTo(ax + Math.cos(angle - 2.5) * 5, ay + Math.sin(angle - 2.5) * 5);
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

        // Soft glow
        if (active) {
            ctx.shadowColor = colors.fill;
            ctx.shadowBlur = 25;
        }

        // Bubble body
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);

        // Gradient fill for 3D bubble effect
        const grad = ctx.createRadialGradient(x - r * 0.25, y - r * 0.25, r * 0.1, x, y, r);
        if (active) {
            grad.addColorStop(0, 'rgba(30, 42, 70, 0.95)');
            grad.addColorStop(1, 'rgba(10, 18, 40, 0.95)');
        } else {
            grad.addColorStop(0, colors.bg.replace(/[\d.]+\)$/, '0.25)'));
            grad.addColorStop(1, colors.bg);
        }
        ctx.fillStyle = grad;
        ctx.fill();

        // Border
        ctx.strokeStyle = colors.border;
        ctx.lineWidth = active ? 2.5 : (node.type === 'diagnosis' ? 2.5 : 1.5);
        ctx.globalAlpha = active ? 1 : 0.75;
        ctx.stroke();
        ctx.globalAlpha = 1;
        ctx.shadowBlur = 0;

        // Specular highlight (bubble shine)
        ctx.beginPath();
        ctx.arc(x - r * 0.22, y - r * 0.28, r * 0.22, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.07)';
        ctx.fill();

        // Label
        ctx.fillStyle = active ? '#ffffff' : colors.fill;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        if (node.type === 'diagnosis') {
            ctx.font = '700 12px var(--font-sans, sans-serif)';
            ctx.fillText(node.shortLabel, x, y - 7);
            ctx.font = '500 11px var(--font-mono, monospace)';
            ctx.fillStyle = active ? '#e2e8f0' : '#475569';
            ctx.fillText(Math.round((node.contribution || 0) * 100) + '%', x, y + 10);
        } else if (r >= 24) {
            ctx.font = '500 10px var(--font-sans, sans-serif)';
            const lines = this._wrapText(node.shortLabel, r * 1.5);
            const lh = 12;
            const sy = y - ((lines.length - 1) * lh) / 2;
            for (let i = 0; i < lines.length; i++) ctx.fillText(lines[i], x, sy + i * lh);
        } else {
            ctx.font = '600 9px var(--font-sans, sans-serif)';
            ctx.fillText(node.shortLabel, x, y);
        }

        // Contribution ring
        if (node.contribution > 0 && node.type !== 'diagnosis') {
            const arcAngle = Math.min(node.contribution * Math.PI * 6, Math.PI * 2);
            ctx.beginPath();
            ctx.arc(x, y, r + 5, -Math.PI / 2, -Math.PI / 2 + arcAngle);
            ctx.strokeStyle = node.supports === false ? '#ff5274' : colors.fill;
            ctx.lineWidth = 2.5;
            ctx.globalAlpha = 0.5;
            ctx.stroke();
        }

        ctx.restore();
    }

    // ── Text helpers ──────────────────────────────────────────────

    _wrapText(text, maxW) {
        const words = text.split(' ');
        const lines = [];
        let current = '';
        for (const w of words) {
            const test = current ? current + ' ' + w : w;
            if (test.length * 5 > maxW && current) { lines.push(current); current = w; }
            else current = test;
        }
        if (current) lines.push(current);
        return lines.slice(0, 3);
    }

    _truncate(text, max) {
        return text.length > max ? text.slice(0, max - 1) + '…' : text;
    }

    // ── Interaction ───────────────────────────────────────────────

    _getCanvasPos(e) {
        const rect = this.canvas.getBoundingClientRect();
        return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    _getNodeAt(px, py) {
        // Check in reverse order so top-drawn nodes have priority
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
            // Move dragged node to mouse position
            this.dragNode.x = pos.x;
            this.dragNode.y = pos.y;
            this.dragNode.vx = 0;
            this.dragNode.vy = 0;
            this.canvas.style.cursor = 'grabbing';

            // Hide tooltip while dragging
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
            // Give a small random kick so it settles naturally
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
            html += `<div style="margin-top:6px;opacity:0.65;font-size:0.7rem;line-height:1.4;">${det}</div>`;
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

    // ── Cleanup ───────────────────────────────────────────────────

    destroy() {
        this.running = false;
    }
}


/* ── Exports ──────────────────────────────────────────────────── */

window.PipelineGraph = PipelineGraph;
window.FindingsGraph = FindingsGraph;


export { PipelineGraph, FindingsGraph };
