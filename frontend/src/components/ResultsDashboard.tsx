"use client";

import { useEffect, useRef } from "react";
import styles from "./ResultsDashboard.module.css";
// @ts-ignore
import { PipelineGraph, FindingsGraph } from "@/lib/graph";

interface ResultsDashboardProps {
  data: any;
  diseaseInput: string;
  onBack: () => void;
}

export default function ResultsDashboard({ data, diseaseInput, onBack }: ResultsDashboardProps) {
  const pipelineCanvasRef = useRef<HTMLCanvasElement>(null);
  const findingsCanvasRef = useRef<HTMLCanvasElement>(null);

  const diag = data.final_diagnosis?.overall || data.diagnosis || {};
  const diagResult = diag.diagnosis || "unknown";
  const confidence = diag.confidence || 0;
  const pct = Math.round(confidence * 100);
  const circumference = 2 * Math.PI * 36;
  const offset = circumference - (confidence * circumference);
  const gaugeColor = confidence >= 0.7 ? "#22C55E" : confidence >= 0.4 ? "#F59E0B" : "#EF4444";

  const chain = diag.reasoning_chain || data.reasoning_trace?.reasoning_chain || [];
  const conceptsData = data.concepts || {};
  const trace = data.pipeline_trace;

  // Flatten concepts
  const allConcepts: any[] = [];
  const seen = new Set();
  for (const stepConcepts of Object.values(conceptsData)) {
    if (Array.isArray(stepConcepts)) {
      for (const c of stepConcepts as any[]) {
        const key = c.name.toLowerCase();
        if (!seen.has(key)) {
          seen.add(key);
          allConcepts.push(c);
        }
      }
    }
  }

  const conceptGroups: Record<string, any[]> = {};
  allConcepts.forEach(c => {
    const cat = (c.category || "finding").toLowerCase();
    if (!conceptGroups[cat]) conceptGroups[cat] = [];
    conceptGroups[cat].push(c);
  });

  const categoryOrder = ['condition', 'finding', 'symptom', 'anatomy', 'measurement'];

  // Init canvas graphs
  useEffect(() => {
    if (pipelineCanvasRef.current && trace) {
      const pGraph = new PipelineGraph(pipelineCanvasRef.current.id);
      pGraph.setTrace(trace);
    }

    if (findingsCanvasRef.current) {
      const fGraph = new FindingsGraph(findingsCanvasRef.current.id);
      fGraph.setData({ diagnosis: diag, reasoningChain: chain, concepts: conceptsData });
    }
  }, []);

  // Gauge animation
  const gaugeFillRef = useRef<SVGCircleElement>(null);
  useEffect(() => {
    if (gaugeFillRef.current) {
      gaugeFillRef.current.style.strokeDashoffset = String(circumference);
      setTimeout(() => {
        if (gaugeFillRef.current) {
          gaugeFillRef.current.style.strokeDashoffset = String(offset);
        }
      }, 100);
    }
  }, [offset, circumference]);

  return (
    <div className={styles.dashboard}>

      {/* ── Tooltip overlays required by graph.js ── */}
      <div id="node-tooltip" className={styles.graphTooltip} style={{ display: "none" }}>
        <div id="tooltip-header" className={styles.tooltipHeader}></div>
        <div id="tooltip-body" className={styles.tooltipBody}></div>
      </div>
      <div id="findings-tooltip" className={styles.graphTooltip} style={{ display: "none" }}>
        <div id="findings-tooltip-header" className={styles.tooltipHeader}></div>
        <div id="findings-tooltip-body" className={styles.tooltipBody}></div>
      </div>

      {/* Header */}
      <div className={styles.header}>
        <button className={styles.backBtn} onClick={onBack}>← Back</button>
        <h2 className={styles.title}>{diseaseInput || "Diagnosis Results"}</h2>
        <span className={`${styles.badge} ${styles[diagResult === "positive" ? "positive" : diagResult === "negative" ? "negative" : "unknown"]}`}>
          {diagResult}
        </span>
      </div>

      {/* Findings Graph */}
      <div className={`${styles.panel} ${styles.graphSection}`}>
        <div className={styles.graphHeader}>
          <h3 className={styles.panelTitle} style={{ marginBottom: 0 }}>Findings Relationship Graph</h3>
          <p className={styles.graphSubtitle}>Drag nodes · hover for details · observations and concepts linked to diagnosis</p>
        </div>
        <canvas id="findings-canvas" ref={findingsCanvasRef} width={800} height={420} className={styles.graphCanvas}></canvas>
        <div className={styles.legend}>
          <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: '#059669' }} /> Diagnosis</span>
          <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: '#0284C7' }} /> Evidence</span>
          <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: '#2563EB' }} /> Finding</span>
          <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: '#E11D48' }} /> Condition</span>
          <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: '#D97706' }} /> Symptom</span>
          <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: '#7C3AED' }} /> Anatomy</span>
          <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: '#059669' }} /> Measurement</span>
          <span className={styles.legendItem}><span className={styles.legendLineDashed} /> Cross-link</span>
        </div>
      </div>

      <div className={styles.grid}>
        <div className={styles.leftCol}>
          {/* Diagnosis */}
          <div className={styles.panel}>
            <h3 className={styles.panelTitle}>Final Diagnosis</h3>
            <div className={styles.gaugeContainer}>
              <div className={styles.gauge}>
                <svg viewBox="0 0 80 80">
                  <circle className={styles.gaugeBg} cx="40" cy="40" r="36" />
                  <circle
                    ref={gaugeFillRef}
                    className={styles.gaugeFill}
                    cx="40" cy="40" r="36"
                    stroke={gaugeColor}
                    strokeDasharray={circumference}
                    strokeDashoffset={circumference}
                  />
                </svg>
                <div className={styles.gaugeLabel}>
                  <span className={styles.gaugeValue} style={{ color: gaugeColor }}>{pct}%</span>
                  <span className={styles.gaugeText}>confidence</span>
                </div>
              </div>
              <div className={styles.verdictText}>
                <h4 style={{ color: gaugeColor }}>
                  {diagResult === 'positive' ? '⚠ Positive' : diagResult === 'negative' ? '✓ Negative' : '? Unknown'}
                </h4>
                <p>{diag.notes || 'No detailed notes provided.'}</p>
              </div>
            </div>

            {diag.evidence && diag.evidence.length > 0 && (
              <div className={styles.evidenceList}>
                {diag.evidence.map((ev: string, i: number) => (
                  <div key={i} className={styles.evidenceItem}><span>›</span> {ev}</div>
                ))}
              </div>
            )}

            {diag.weights && diag.weights.length > 0 && (
              <div className={styles.weightsGrid}>
                {diag.weights.map((w: any, i: number) => (
                  <span key={i} className={styles.weightTag}>
                    {w.indicator_name} <span className={styles.weightValue}>{(w.weight * 100).toFixed(0)}%</span>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Reasoning Chain */}
          <div className={styles.panel}>
            <h3 className={styles.panelTitle}>Reasoning Chain</h3>
            {chain.length > 0 ? chain.map((step: any, i: number) => {
              const supports = step.supports_diagnosis !== false;
              const contrib = step.confidence_contribution || 0;
              const barW = Math.min(Math.abs(contrib) * 500, 100);

              return (
                <div key={i} className={styles.reasoningStep}>
                  <div className={styles.stepHeader}>
                    <span>{step.observation || "—"}</span>
                    <span className={`${styles.stepContrib} ${supports ? '' : styles.negative}`}>
                      {supports ? '+' : '−'}{(Math.abs(contrib) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className={styles.stepSig}>{step.clinical_significance}</div>
                  <div className={styles.stepBar}>
                    <div className={`${styles.stepBarFill} ${supports ? '' : styles.negative}`} style={{ width: `${barW}%` }}></div>
                  </div>
                </div>
              );
            }) : <p>No reasoning data.</p>}
          </div>
        </div>

        <div className={styles.rightCol}>
          {/* Stats */}
          <div className={styles.panel}>
            <h3 className={styles.panelTitle}>Pipeline Stats</h3>
            <div className={styles.statsGrid}>
              <div className={styles.statCard}>
                <span className={styles.statLabel}>Total Time</span>
                <span className={styles.statValue}>{(trace?.total_duration_seconds || 0).toFixed(1)}s</span>
              </div>
              <div className={styles.statCard}>
                <span className={styles.statLabel}>Nodes</span>
                <span className={styles.statValue}>{trace?.nodes?.length || 0}</span>
              </div>
              <div className={styles.statCard}>
                <span className={styles.statLabel}>Completed</span>
                <span className={styles.statValue} style={{color: gaugeColor}}>
                  {trace?.nodes?.filter((n: any) => n.status === 'completed').length || 0}
                </span>
              </div>
              <div className={styles.statCard}>
                <span className={styles.statLabel}>Errors</span>
                <span className={styles.statValue} style={{color: '#EF4444'}}>
                  {trace?.nodes?.filter((n: any) => n.status === 'error').length || 0}
                </span>
              </div>
            </div>
          </div>

          {/* Pipeline Graph */}
          <div className={`${styles.panel} ${styles.graphSection}`}>
            <div className={styles.graphHeader}>
              <h3 className={styles.panelTitle} style={{ marginBottom: 0 }}>Pipeline Execution</h3>
              <p className={styles.graphSubtitle}>Hover over nodes for step details</p>
            </div>
            <canvas id="pipeline-canvas" ref={pipelineCanvasRef} width={280} height={480} className={styles.graphCanvas}></canvas>
            <div className={styles.legend}>
              <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: '#2563EB' }} /> Completed</span>
              <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: '#2563EB', boxShadow: '0 0 6px rgba(37,99,235,0.5)' }} /> Running</span>
              <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: '#E11D48' }} /> Error</span>
              <span className={styles.legendItem}><span className={styles.legendDot} style={{ background: '#CBD5E1' }} /> Pending</span>
            </div>
          </div>

          {/* Medical Concepts */}
          <div className={styles.panel}>
            <h3 className={styles.panelTitle}>Medical Concepts</h3>
            {allConcepts.length > 0 ? (
              categoryOrder.map(cat => (
                conceptGroups[cat] && conceptGroups[cat].length > 0 ? (
                  <div key={cat} className={styles.conceptCategory}>
                    <h4><span className={`${styles.categoryDot} ${styles[cat]}`}></span> {cat}s ({conceptGroups[cat].length})</h4>
                    <div className={styles.conceptTags}>
                      {conceptGroups[cat].map((c, i) => (
                        <span key={i} className={styles.conceptTag} title={c.relevance || c.original_text}>
                          {c.name}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null
              ))
            ) : <p>No concepts extracted.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
