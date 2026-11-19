# Adding everything to your project: step by step

Do these in order. Stop at the first step that fails and tell Claude the exact message.

## A. Keep a safe copy first
In your project folder (the one with `backend` and `frontend`), in the VS Code terminal:

    git status
    git add -A
    git commit -m "Before multi-app update"
    git checkout -b multi-app

Now every change below happens on a separate branch called `multi-app`. If anything goes wrong,
`git checkout main` brings the old working app back.

## B. Put the new files in
1. Unzip `readaloud-all-stages.zip` somewhere else first (for example your Desktop).
2. Open the unzipped folder, select everything inside it (the folders `backend`, `frontend`,
   `frontend-admin`, `frontend-stt`, `docs` and the files `Dockerfile`, `render.yaml`, `README.md`).
3. Copy them into your project folder. When asked, choose "Replace the files in the destination".
4. Back in VS Code: `git status` shows what changed. `git diff` lets you review any file. Nothing of
   yours is lost: the old versions are in git.

## C. Settings (backend/.env)
Open `backend/.env` and add these lines (keep the ones you already have):

    ADMIN_EMAILS=your-email@example.com
    DEFAULT_APPS=library
    GROQ_API_KEY=your-groq-key
    TRANSCRIBE_ENGINE=groq
    STORAGE_BACKEND=local

`ADMIN_EMAILS` must be the email you sign in with. Do not share the Groq key with anyone.

## D. Install what is new
Backend (in `backend`, with `(.venv)` showing):

    pip install -r requirements.txt

ffmpeg (needed to cut long recordings). In PowerShell:

    winget install ffmpeg

Close and reopen VS Code afterwards, then check with `ffmpeg -version`.

## E. Build the three screens (each folder once)

    cd frontend
    npm install
    npm run build
    cd ../frontend-admin
    npm install
    npm run build
    cd ../frontend-stt
    npm install
    npm run build

## F. Start it

    cd ../backend
    python -m uvicorn app.main:app --port 8000

Open http://localhost:8000. If the server stops with an error, copy the last red line.
Database changes (new tables and columns) are applied automatically at start.

## G. Test in layers (tick each one)
Layer 1: what you already had
- [ ] Sign in works and the library opens (you may land on /admin/: that is expected, see Layer 2).
- [ ] Upload a PDF, press Listen, voice and notes still work.

Layer 2: roles and admin
- [ ] Signing in with your admin email lands on /admin/.
- [ ] Admin > Add people: add a second email with Library only.
- [ ] In a private window, create that account (no invite code needed). It opens the library, not admin.
- [ ] Admin > People: switch Library off for that person. Refresh their window: they are sent away.

Layer 3: groups, books and usage
- [ ] Admin > Groups: create "Test group" and add the second person.
- [ ] Admin > Books: upload a PDF, then "Who can read" > pick the group > Save.
- [ ] In the second person's library the book shows "Shared with you". They can read it and write notes.
      They cannot delete it. Their reading position is their own.
- [ ] Admin > Usage: after a few minutes of reading it shows the opens, the book and the person.

Layer 4: transcription
- [ ] Add Transcribe for the second person (Admin > People), or open /transcribe/ as admin.
- [ ] Upload a 2 to 3 minute recording. It finishes, opens in the editor and plays in sync.
- [ ] Export to Word works.
- [ ] Only then try a long sermon.

## H. Save your work

    git add -A
    git commit -m "Library, Transcribe and Admin in one app"

## I. Going live (only after Layer 1 to 4 pass on your computer)
1. Push the branch: `git push -u origin multi-app`.
2. In Render, create a second free web service from the `multi-app` branch for testing. Set the
   same Environment values as your main one, plus ADMIN_EMAILS and GROQ_API_KEY. Use a new
   INVITE_CODE value that is not written in any file.
3. Test there. When it behaves, merge `multi-app` into `main` and your main service redeploys.

## J. Two things to decide soon
- Database: Render's free database is deleted after 30 days. Move to a free external one (Neon) before then.
- Files: a free host forgets uploaded PDFs on restart. For permanent books, create a bucket and set
  STORAGE_BACKEND=s3 with the S3_ values (ask Claude to walk you through it).
