"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import Sidebar from "@/components/Sidebar";
import DiagnosisForm from "@/components/DiagnosisForm";
import ProgressOverlay from "@/components/ProgressOverlay";
import styles from "./page.module.css";

const ResultsDashboard = dynamic(() => import("@/components/ResultsDashboard"), {
  ssr: false,
});

export default function Home() {
  const [selectedRecord, setSelectedRecord] = useState<{ disease: string; record: string } | null>(null);
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzingDisease, setAnalyzingDisease] = useState("");
  const [activeNode, setActiveNode] = useState("");

  const handleSelectRecord = async (disease: string, record: string) => {
    if (!disease || !record) {
      setSelectedRecord(null);
      setDashboardData(null);
      setErrorMsg(null);
      return;
    }

    try {
      setErrorMsg(null);
      const res = await fetch(`/api/results/${disease}/${record}`);
      // Guard against non-JSON responses
      const contentType = res.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        throw new Error(`Server error: ${res.status} ${res.statusText}`);
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to load result");
      setSelectedRecord({ disease, record });
      setDashboardData(data);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "Failed to load result.");
    }
  };

  const handleDiagnosisStart = (disease: string) => {
    setErrorMsg(null);
    setIsAnalyzing(true);
    setAnalyzingDisease(disease);
    setActiveNode("load_config"); // Default first step
  };

  const handleProgress = (node: string) => {
    setActiveNode(node);
  };

  const handleDiagnosisSuccess = (data: any, disease: string) => {
    setIsAnalyzing(false);
    setSelectedRecord({ disease, record: "latest" });
    setDashboardData(data);
  };

  const handleDiagnosisError = (err: string) => {
    setIsAnalyzing(false);
    setErrorMsg(err);
  };

  return (
    <div className={styles.container}>
      <Sidebar onSelectRecord={handleSelectRecord} />

      <main className={styles.mainContent}>
        {errorMsg && (
          <div className={styles.errorAlert}>
            <strong>Error:</strong> {errorMsg}
            <button onClick={() => setErrorMsg(null)}>✕</button>
          </div>
        )}

        {!dashboardData ? (
          <DiagnosisForm
            onSubmitStart={handleDiagnosisStart}
            onProgress={handleProgress}
            onSubmitSuccess={handleDiagnosisSuccess}
            onSubmitError={handleDiagnosisError}
          />
        ) : (
          <ResultsDashboard
            data={dashboardData}
            diseaseInput={selectedRecord?.disease || ""}
            onBack={() => {
              setSelectedRecord(null);
              setDashboardData(null);
            }}
          />
        )}
      </main>

      {/* Progress overlay: shown while the POST /api/diagnose is in-flight */}
      <ProgressOverlay visible={isAnalyzing} disease={analyzingDisease} activeNode={activeNode} />
    </div>
  );
}
