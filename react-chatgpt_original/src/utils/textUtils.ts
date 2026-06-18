/**
 * Shared utility functions for text processing
 */

/**
 * Removes orchestration markers like STOP/FINAL ANSWER from text
 */
export function cleanText(text: string): string {
  return text
    .replace(/^\s*(?:STOP|FINAL\s*ANSWER)\s*:?\s*/i, '')
    .replace(/\s*(?:STOP|FINAL\s*ANSWER)\s*:?\s*$/i, '')
    .trim();
}

/**
 * Converts a file to a data URL string
 */
export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}
