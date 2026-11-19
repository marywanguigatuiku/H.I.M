import { api } from "./api";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Sends the recording in small pieces. Safe to call again after a failure: pieces the server already has are skipped. */
export async function uploadRecording(file, jobId, partSize, onProgress) {
  const state = await api(`/api/transcriptions/${jobId}/upload`);
  const have = new Set(state.received_parts);
  const total = Math.max(1, Math.ceil(file.size / partSize));
  let sent = have.size;
  onProgress(sent / total);
  for (let n = 0; n < total; n++) {
    if (have.has(n)) continue;
    const piece = file.slice(n * partSize, (n + 1) * partSize);
    let attempt = 0;
    for (;;) {
      try {
        await api(`/api/transcriptions/${jobId}/parts/${n}`, { method: "PUT", binary: piece });
        break;
      } catch (err) {
        attempt++;
        if ((err.status && err.status < 500) || attempt >= 4) throw err; // real errors stop; network hiccups retry
        await sleep(1500 * attempt);
      }
    }
    sent++;
    onProgress(sent / total);
  }
  return api(`/api/transcriptions/${jobId}/complete`, { method: "POST", body: { parts: total } });
}
