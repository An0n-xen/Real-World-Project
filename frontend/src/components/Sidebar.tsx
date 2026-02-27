"use client";

import { useEffect, useState } from "react";
import styles from "./Sidebar.module.css";

interface DiagnosisResult {
  disease: string;
  record: string;
  has_trace: boolean;
  start_time: string;
  patient_context: string;
}

interface SidebarProps {
  onSelectRecord?: (disease: string, record: string) => void;
}

export default function Sidebar({ onSelectRecord }: SidebarProps) {
  const [history, setHistory] = useState<DiagnosisResult[] | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchHistory = async () => {
    try {
      const res = await fetch("/api/results");
      const data = await res.json();
      setHistory(data);
    } catch (err) {
      console.error("Failed to load history", err);
      setHistory([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    const interval = setInterval(fetchHistory, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className={styles.sidebar}>
      <div className={styles.header}>
        <div className={styles.logoGroup}>
          <div className={styles.logoIcon}>M+</div>
          <div>
            <div className={styles.title}>MedAgent</div>
            <div className={styles.tagline}>Pro Diagnostics</div>
          </div>
        </div>

        <nav className={styles.nav}>
          <button
            className={`${styles.navBtn} ${styles.active}`}
            onClick={() => onSelectRecord?.("", "")}
          >
            <span className={styles.navIcon}>＋</span>
            New Diagnosis
          </button>
        </nav>
      </div>

      <div className={styles.historySection}>
        <div className={styles.sectionTitle}>History</div>
        <div className={styles.resultsList}>
          {loading ? (
            <p className={styles.placeholderText}>Loading…</p>
          ) : history && history.length > 0 ? (
            history.map((r, i) => (
              <div
                key={`${r.disease}-${r.record}-${i}`}
                className={styles.resultItem}
                onClick={() => onSelectRecord?.(r.disease, r.record)}
              >
                <span className={styles.resultIcon}>🔬</span>
                <div className={styles.resultInfo}>
                  <div className={styles.diseaseName}>
                    {r.disease.replace(/_/g, " ")}
                  </div>
                  <div className={styles.recordMeta}>
                    {r.start_time
                      ? new Date(r.start_time).toLocaleDateString(undefined, { month: "short", day: "numeric" })
                      : r.record}
                  </div>
                </div>
                <span className={styles.resultArrow}>›</span>
              </div>
            ))
          ) : (
            <p className={styles.placeholderText}>No diagnoses yet.</p>
          )}
        </div>
      </div>

      <div className={styles.sidebarFooter}>
        <div className={styles.footerStatus}>
          <span className={styles.statusDot}></span>
          AI Pipeline Active
        </div>
      </div>
    </aside>
  );
}
