"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import Sidebar from "@/components/Sidebar";
import DiagnosisForm from "@/components/DiagnosisForm";
import styles from "./page.module.css";

const ResultsDashboard = dynamic(() => import("@/components/ResultsDashboard"), {
  ssr: false,
});

export default function Home() {
  const [selectedRecord, setSelectedRecord] = useState<{ disease: string; record: string } | null>(null);
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSelectRecord = async (disease: string, record: string) => {
    if (!disease || !record) {
      // New diagnosis view
      setSelectedRecord(null);
      setDashboardData(null);
      setErrorMsg(null);
      return;
    }

    try {
      setErrorMsg(null);
      const res = await fetch(`/api/results/${disease}/${record}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to load result");
      setSelectedRecord({ disease, record });
      setDashboardData(data);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "Failed to load result.");
    }
  };

  const handleDiagnosisStart = () => {
    setErrorMsg(null);
  };

  const handleDiagnosisSuccess = (data: any, disease: string) => {
    // When diagnosis completes, we show it via dashboardData
    setSelectedRecord({ disease, record: "latest" }); // arbitrary record name, data serves the dashboard
    setDashboardData(data);
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
            onSubmitSuccess={handleDiagnosisSuccess}
            onSubmitError={setErrorMsg}
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
    </div>
  );
}
