"use client";
import { useEffect, useState } from "react";
import styles from "./ProgressOverlay.module.css";

const STAGES = [
  { key: "load_config",         label: "Loading Config",           desc: "Loading disease configuration and toolset" },
  { key: "retrieve_guidelines", label: "Retrieving Guidelines",    desc: "RAG-retrieving relevant medical literature" },
  { key: "generate_plan",       label: "Generating Plan",          desc: "Building the diagnostic execution plan" },
  { key: "generate_tools",      label: "Generating Tools",         desc: "Compiling quantitative analysis tools" },
  { key: "execute_steps",       label: "Executing Analysis",       desc: "Running multi-modal diagnostic steps" },
  { key: "collect_indicators",  label: "Collecting Indicators",    desc: "Aggregating diagnostic indicators" },
  { key: "final_decision",      label: "Final Decision",           desc: "Decider agent producing final diagnosis" },
];

interface ProgressOverlayProps {
  disease: string;
  visible: boolean;
  activeNode: string;
}

export default function ProgressOverlay({ disease, visible, activeNode }: ProgressOverlayProps) {
  const [elapsed, setElapsed] = useState(0);

  // Find the index of the currently active node
  const currentStage = STAGES.findIndex(s => s.key === activeNode) || 0;

  // Elapsed counter only
  useEffect(() => {
    if (!visible) {
      setElapsed(0);
      return;
    }
    const tick = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(tick);
  }, [visible]);

  if (!visible) return null;

  return (
    <div className={styles.overlay}>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.pulsingDot}></div>
          <div>
            <h2 className={styles.title}>Analyzing</h2>
            <p className={styles.subtitle}>{disease || "Condition"}</p>
          </div>
          <div className={styles.timer}>{elapsed}s</div>
        </div>

        <div className={styles.stages}>
          {STAGES.map((stage, i) => {
            const done    = i < currentStage;
            const active  = i === currentStage;
            const waiting = i > currentStage;
            return (
              <div key={stage.key} className={`${styles.stage} ${done ? styles.done : active ? styles.active : styles.waiting}`}>
                <div className={styles.stageLeft}>
                  <div className={styles.stageIcon}>
                    {done ? (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
                    ) : active ? (
                      <span className={styles.activeSpinner}></span>
                    ) : (
                      <span className={styles.stageNum}>{String(i + 1).padStart(2, "0")}</span>
                    )}
                  </div>
                  <div className={styles.stageConnector}></div>
                </div>
                <div className={styles.stageBody}>
                  <div className={styles.stageName}>{stage.label}</div>
                  {active && <div className={styles.stageDesc}>{stage.desc}</div>}
                </div>
              </div>
            );
          })}
        </div>

        <div className={styles.footer}>
          <div className={styles.progressBar}>
            <div className={styles.progressFill} style={{ width: `${((currentStage + 1) / STAGES.length) * 100}%` }}></div>
          </div>
          <span className={styles.progressText}>{currentStage + 1} / {STAGES.length} stages</span>
        </div>
      </div>
    </div>
  );
}
