# GameCUA website

Project page for GameCUA (Vite + TypeScript + three.js). This branch holds only the site.

```bash
npm install
python tools/build_assets.py <paper_dir> <data_dir>   # regenerate public/img and src/data.json (optional; outputs are committed)
npm run dev        # local preview
npm run build      # static site in dist/
```

`<paper_dir>` is the Overleaf paper checkout; `<data_dir>` holds the trial subset from the `Zhuhan/GameCUA` Hugging Face dataset (`picked.json`, `replays.json`, `posters/`).
