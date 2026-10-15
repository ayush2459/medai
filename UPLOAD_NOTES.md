# Upload notes

This repository was initialized for the MedIntel AI sprint project. The original uploaded archive was `medintel-ai-sprint3(1).zip` and contains a `frontend/` React + TypeScript/Vite app and a `backend/` FastAPI app, migrations, models, and ICU-risk ML code.

To upload the full binary-safe project via SSH from your Mac, extract the archive, navigate to the project root, inspect `.gitignore` and remove any credentials, then run:

```bash
git init
git branch -M main
git remote add origin git@github.com:ayush2459/medai.git
git add .
git status
git commit -m "Initial MedIntel AI project"
git push -u origin main
```

If cloning this repository first, `git clone git@github.com:ayush2459/medai.git` and copy the extracted project files into the cloned directory instead, preserving this note and README. Do not commit live `.env` files, secrets, or actual patient data.