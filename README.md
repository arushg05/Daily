# Asymptote-LT

This repository contains the Asymptote-LT scanner (backend Python) and a React + Vite frontend in `frontend/`.

Quick local notes:

- Backend: `backend/` (Python). Run the scanner with:

```powershell
cd backend
py -3 main.py
```

- Frontend: `frontend/` (Vite + React + TypeScript). Start dev server:

```bash
cd frontend
npm install
npm run dev
```

Deploying to GitHub & Vercel
- Using GitHub CLI (if installed and authenticated):

```bash
cd /path/to/repo
gh repo create asymptote-lt --public --source=. --remote=origin --push --confirm
```

- To deploy on Vercel (connect your GitHub repo in the Vercel dashboard):
  - Import the GitHub repo in Vercel.
  - Set the project root to `frontend`.
  - Build command: `npm run build` and Output Directory: `dist`.

- Or use Vercel CLI from the `frontend` folder (requires login):

```bash
cd frontend
npx vercel --prod --confirm
```

If the GitHub CLI is not available, create a repo on github.com, add the `origin` remote and push:

```bash
git remote add origin https://github.com/<YOUR_USER>/<REPO>.git
git push -u origin main
```

Contact me if you want me to attempt the GitHub creation and Vercel deploy from this environment.
