import { useCallback, useEffect, useState, type ClipboardEvent, type DragEvent } from 'react';
import { uploadChatAttachments } from '../lib/api';
import { attachmentMessage, toErrorMessage } from '../lib/format';

export type PendingFile = { id: string; file: File; previewUrl: string | null };

function revokePreviews(files: PendingFile[]) {
  files.forEach((f) => { if (f.previewUrl) URL.revokeObjectURL(f.previewUrl); });
}

/**
 * Manages a list of files staged for upload, with image previews and the
 * drag/drop + paste handlers used by the chat composers. Object URLs are
 * revoked on removal and on unmount.
 */
export function useFileAttachments() {
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const addFiles = useCallback((files: FileList | File[]) => {
    const next: PendingFile[] = Array.from(files).map((file) => ({
      id: crypto.randomUUID(),
      file,
      previewUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : null,
    }));
    if (next.length > 0) setPendingFiles((prev) => [...prev, ...next]);
  }, []);

  const removeFile = useCallback((id: string) => {
    setPendingFiles((prev) => {
      const target = prev.find((f) => f.id === id);
      if (target) revokePreviews([target]);
      return prev.filter((f) => f.id !== id);
    });
  }, []);

  const clearFiles = useCallback(() => {
    setPendingFiles((prev) => {
      revokePreviews(prev);
      return [];
    });
  }, []);

  useEffect(() => clearFiles, [clearFiles]);

  const submitWithAttachments = useCallback(async (taskId: string, text: string): Promise<string | null> => {
    if (pendingFiles.length === 0) return text;
    setUploadError(null);
    try {
      const filePaths = await uploadChatAttachments(taskId, pendingFiles.map((f) => f.file));
      clearFiles();
      return attachmentMessage(text, filePaths);
    } catch (err) {
      setUploadError(toErrorMessage(err, 'Failed to upload files'));
      return null;
    }
  }, [clearFiles, pendingFiles]);

  const onDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.types.includes('Files')) setDragOver(true);
  }, []);

  const onDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    if (e.relatedTarget && (e.currentTarget as Node).contains(e.relatedTarget as Node)) return;
    setDragOver(false);
  }, []);

  const onDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) addFiles(e.dataTransfer.files);
  }, [addFiles]);

  const handlePaste = useCallback((e: ClipboardEvent) => {
    const files = Array.from(e.clipboardData.items)
      .filter((item) => item.kind === 'file')
      .map((item) => item.getAsFile())
      .filter((f): f is File => f !== null);
    if (files.length > 0) {
      e.preventDefault();
      addFiles(files);
    }
  }, [addFiles]);

  return {
    pendingFiles,
    dragOver,
    uploadError,
    setUploadError,
    addFiles,
    removeFile,
    clearFiles,
    submitWithAttachments,
    dragHandlers: { onDragOver, onDragLeave, onDrop },
    handlePaste,
  };
}
