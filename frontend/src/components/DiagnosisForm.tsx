"use client";

import { useState, useEffect, DragEvent, ChangeEvent, FormEvent, useRef } from "react";
import styles from "./DiagnosisForm.module.css";

interface DiagnosisFormProps {
  onSubmitStart: () => void;
  onSubmitSuccess: (data: any, disease: string) => void;
  onSubmitError: (err: string) => void;
}

export default function DiagnosisForm({ onSubmitStart, onSubmitSuccess, onSubmitError }: DiagnosisFormProps) {
  const [diseases, setDiseases] = useState<any[]>([]);
  const [diseaseInput, setDiseaseInput] = useState("");
  const [contextInput, setContextInput] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch("/api/diseases")
      .then(res => res.json())
      .then(data => setDiseases(data))
      .catch(console.error);
  }, []);

  const handleImageChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      const file = e.target.files[0];
      setImageFile(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const clearImage = () => {
    setImageFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => { e.preventDefault(); setIsDragOver(true); };
  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => { e.preventDefault(); setIsDragOver(false); };
  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); setIsDragOver(false);
    if (e.dataTransfer.files?.[0]) {
      const file = e.dataTransfer.files[0];
      setImageFile(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (isSubmitting || !diseaseInput.trim()) return;
    setIsSubmitting(true);
    onSubmitStart();

    const formData = new FormData();
    formData.append("disease", diseaseInput);
    if (contextInput) formData.append("patient_context", contextInput);
    if (imageFile) formData.append("image", imageFile);

    try {
      const res = await fetch("/api/diagnose", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) onSubmitError(data.error || "Unknown error");
      else onSubmitSuccess(data, diseaseInput);
    } catch (err: any) {
      onSubmitError(err.message || "Network error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={styles.page}>

      <div className={styles.heroSection}>
        <div className={styles.heroBadge}>
          <span className={styles.heroNumber}>AI</span>
          <span>Diagnostic Engine</span>
        </div>
        <h1 className={styles.heroTitle}>
          MedAgent <span style={{ color: "#CAFF00", WebkitTextStroke: "2px #0D0E12" }}>Pro</span>
        </h1>
      </div>

      <form onSubmit={handleSubmit} className={styles.form}>

        {/* Step 1 — Disease Input */}
        <div className={styles.fieldBlock}>
          <div className={styles.fieldMeta}>
            <span className={styles.stepNum}>01</span>
            <label className={styles.fieldLabel} htmlFor="disease-input">Disease or Condition</label>
          </div>
          <div className={styles.inputWrap}>
            <input
              ref={inputRef}
              type="text"
              id="disease-input"
              className={styles.bigInput}
              placeholder="Type a condition…"
              value={diseaseInput}
              onChange={(e) => setDiseaseInput(e.target.value)}
              required
              autoComplete="off"
            />
            {diseaseInput && (
              <button type="button" className={styles.clearBtn} onClick={() => setDiseaseInput("")} aria-label="Clear">✕</button>
            )}
          </div>

          {diseases.length > 0 && (
            <div className={styles.quickPicks}>
              <span className={styles.quickPicksLabel}>Quick picks</span>
              <div className={styles.quickPicksRow}>
              {diseases.slice(0, 6).map((d, i) => {
                  const raw: string = d.disease || d.name || "";
                  const label = raw.replace(/^diagnose\s+potential\s+/i, "").trim();
                  return (
                    <button
                      key={i}
                      type="button"
                      className={`${styles.quickPick} ${diseaseInput === raw ? styles.active : ""}`}
                      onClick={() => setDiseaseInput(raw)}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Divider */}
        <div className={styles.divider}></div>

        {/* Step 2 — Context */}
        <div className={styles.fieldBlock}>
          <div className={styles.fieldMeta}>
            <span className={styles.stepNum}>02</span>
            <label className={styles.fieldLabel} htmlFor="context-input">
              Patient Context
              <span className={styles.optional}> — optional but improves accuracy</span>
            </label>
          </div>
          <textarea
            id="context-input"
            className={styles.textarea}
            rows={4}
            placeholder="Age, comorbidities, symptoms, duration, lab values…"
            value={contextInput}
            onChange={(e) => setContextInput(e.target.value)}
          ></textarea>
        </div>

        {/* Divider */}
        <div className={styles.divider}></div>

        {/* Step 3 — Image */}
        <div className={styles.fieldBlock}>
          <div className={styles.fieldMeta}>
            <span className={styles.stepNum}>03</span>
            <label className={styles.fieldLabel}>
              Medical Image
              <span className={styles.optional}> — optional</span>
            </label>
          </div>

          {!previewUrl ? (
            <div
              className={`${styles.dropZone} ${isDragOver ? styles.dropZoneActive : ""}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <input type="file" className={styles.fileInput} accept="image/*" onChange={handleImageChange} />
              <div className={styles.dropZoneInner}>
                <div className={styles.dropIcon}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                </div>
                <div>
                  <span className={styles.dropPrimary}>Click to upload</span>
                  <span className={styles.dropSecondary}> or drag and drop</span>
                </div>
                <span className={styles.dropFormats}>PNG · JPG · DICOM</span>
              </div>
            </div>
          ) : (
            <div className={styles.previewWrap}>
              <img src={previewUrl} alt="Preview" className={styles.previewImg} />
              <div className={styles.previewActions}>
                <span className={styles.previewName}>{imageFile?.name}</span>
                <button type="button" className={styles.removeBtn} onClick={clearImage}>Remove</button>
              </div>
            </div>
          )}
        </div>

        {/* Submit */}
        <div className={styles.submitRow}>
          <button type="submit" className={styles.submitBtn} disabled={isSubmitting || !diseaseInput.trim()}>
            {isSubmitting ? (
              <span className={styles.submittingState}>
                <span className={styles.spinner}></span>
                Running analysis…
              </span>
            ) : (
              <span className={styles.submitLabel}>
                Run Diagnostic
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              </span>
            )}
          </button>
          <p className={styles.submitNote}>Results typically ready in 15–60 seconds</p>
        </div>

      </form>
    </div>
  );
}
