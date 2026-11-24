# GameCUA V1 Experiment Records (slim)

This branch holds the 156 trials of GameCUA V1 without their media: six agents on fifteen commercial games. The complete records, with screenshots and screen recordings, are in the Hugging Face dataset [`Zhuhan/GameCUA-V1-Exp`](https://huggingface.co/datasets/Zhuhan/GameCUA-V1-Exp). The starting states of the trials are in the `snapshots/` directory on `main`.

## Layout

```
<game>/<agent>/<mode>/final/...         the trial's files, at the same paths as in the dataset
<game>/<agent>/<mode>/OMITTED.json.gz   every file that is only in the dataset: path, size, git blob id, LFS sha256
cells.json                              one entry per trial: trial id, specification, end, rubric, rubric score, file counts
```

`<mode>` is `live` or `frozen`; the four turn-based games have `live` only. `end` in `cells.json` is how the trial ended: `budget` (the time budget ran out), `death` (the first native death) or `stopped` (the trial was ended before its budget). The dataset card describes the agents, the games and the files of a trial.

## What is in the dataset only

Screenshots and screen recordings (`*.png`, `*.jpg`, `*.jpeg`, `*.webp`, `*.mp4`, `*.gif`, `*.bmp`), the native telemetry of art of rally (`art-of-rally/**/*.native.json*`, about 8 GB) and machine-local files (`*.local.json`). Together they are about 153 GB. Everything else is here, about 1.1 GB: specifications, rubrics, score files, interviews, per-decision records, event logs, context databases and native game saves.

Every file here is byte-identical to the dataset; each was checked against the dataset's git blob id or LFS sha256. The files that are only in the dataset can be checked against `OMITTED.json.gz`.

The frozen trial of Jev 1.14.0 on Left 4 Dead 2 is a single archive in the dataset, `left-4-dead-2/jev-1-14/frozen/full-record/l4d2-jev-frozen-full-record.tar` (sha256 `aa47b1fa9c9c9643351f6b975505cd9b54c40b258f37fb63ccfd80379da23a18`). Here it is unpacked into `final/`, and `OMITTED.json.gz` lists each member left out as `<archive path>::<member path>`.

## Scores

`hf_score` in `cells.json` is the rubric score recorded in the trial's `CELL.json`: the sum of the designer weights of the verified milestones. The scores reported in the GameCUA paper apply the difficulty-tier weights to the same verified milestones.
