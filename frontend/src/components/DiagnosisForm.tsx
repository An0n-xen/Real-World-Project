"use client";

import { useState, useEffect, DragEvent, ChangeEvent, FormEvent } from "react";
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
    <div className={styles.formCard}>
      <div className={styles.pageHeader}>
        <h1 className={styles.pageTitle}>Run Diagnosis</h1>
        <p className={styles.pageSubtitle}>Enter a disease or condition and optionally provide patient context and imaging.</p>
      </div>

      <div className={styles.card}>
        <form onSubmit={handleSubmit}>
          <div className={styles.formGroup}>
            <label className={styles.label} htmlFor="disease-input">Disease / Condition</label>
            <input
              type="text"
              id="disease-input"
              className={styles.input}
              placeholder="e.g. diabetic retinopathy, tuberculosis, glaucoma…"
              value={diseaseInput}
              onChange={(e) => setDiseaseInput(e.target.value)}
              required
              autoComplete="off"
            />
            {diseases.length > 0 && (
              <div className={styles.inputHint}>
                {diseases.map((d, i) => (
                  <span key={i} className={styles.suggestion} onClick={() => setDiseaseInput(d.disease || d.name)}>
                    {d.disease || d.name}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label} htmlFor="context-input">
              Patient Context <span className={styles.optional}>(optional)</span>
            </label>
            <textarea
              id="context-input"
              className={styles.textarea}
              rows={4}
              placeholder="e.g. 55-year-old male, Type 2 diabetes for 10 years, HbA1c 8.2%, blurred vision in both eyes…"
              value={contextInput}
              onChange={(e) => setContextInput(e.target.value)}
            ></textarea>
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label}>
              Medical Image <span className={styles.optional}>(optional)</span>
            </label>
            <div
              className={`${styles.fileUpload} ${isDragOver ? styles.dragover : ""}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              {!previewUrl ? (
                <>
                  <input type="file" className={styles.fileInput} accept="image/*" onChange={handleImageChange} />
                  <div className={styles.uploadPlaceholder}>
                    <span className={styles.uploadIcon}>📎</span>
                    <strong>Drop image here or click to upload</strong>
                    <span>Supports PNG, JPG, DICOM</span>
                  </div>
                </>
              ) : (
                <div className={styles.uploadPreview}>
                  <img src={previewUrl} alt="Preview" className={styles.previewImg} />
                  <button type="button" className={styles.removeBtn} onClick={clearImage}>✕</button>
                </div>
              )}
            </div>
          </div>

          <button type="submit" className={styles.btnPrimary} disabled={isSubmitting}>
            {isSubmitting ? (
              <><span className={styles.loader}></span> Analyzing…</>
            ) : (
              "Run Diagnostic →"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
