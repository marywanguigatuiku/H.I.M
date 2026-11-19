// Keeps the original recording on this device so the editor can play it even after the server forgets it.
function open() {
  return new Promise((resolve, reject) => {
    const r = indexedDB.open("readaloud-stt", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("audio");
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });
}
async function run(mode, fn) {
  const db = await open();
  return new Promise((resolve, reject) => {
    const t = db.transaction("audio", mode);
    const req = fn(t.objectStore("audio"));
    t.oncomplete = () => { db.close(); resolve(req ? req.result : undefined); };
    t.onerror = () => { db.close(); reject(t.error); };
    t.onabort = () => { db.close(); reject(t.error); };
  });
}
export const saveAudio = (id, file) => run("readwrite", (s) => s.put(file, id));
export const getAudio = (id) => run("readonly", (s) => s.get(id));
export const deleteAudio = (id) => run("readwrite", (s) => s.delete(id));
