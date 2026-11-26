# GameCUA website

Project page for GameCUA (Vite + TypeScript + three.js). This branch holds only the site. It is published at https://touchstone-ai-lab.github.io/bench-gamecua/ by the workflow in
[Touchstone-AI-Lab.github.io](https://github.com/Touchstone-AI-Lab/Touchstone-AI-Lab.github.io), which rebuilds from this branch within
15 minutes of a push (`gh workflow run pages.yml -R Touchstone-AI-Lab/Touchstone-AI-Lab.github.io` publishes at once). This repo's own
Pages (`/GameCUA/`) only redirects there.

```bash
npm install
python tools/build_assets.py <paper_dir> <data_dir>   # regenerate public/img and src/data.json (optional; outputs are committed)
python tools/build_replays.py <data_dir> <cache_dir>  # regenerate public/video and src/replays.json (optional; outputs are committed)
npm run dev        # local preview
npm run build      # static site in dist/
```

`<paper_dir>` is the Overleaf paper checkout; `<data_dir>` holds the trial subset from the `Zhuhan/GameCUA` Hugging Face dataset (`picked.json`, `replays.json`, `posters/`).
