// Typed view of data.json, which tools/build_assets.py generates from the paper and the trial data.
import raw from './data.json';

export type Action = {
  type: string; keys?: string[]; duration?: number; buttons?: string[]; dx?: number; dy?: number;
  x?: number; y?: number; button?: string; to_x?: number; to_y?: number; seconds?: number; text?: string;
};
export type Step = { observation: string; hypothesis: string; action: Action; decision: number };
export type Game = {
  slug: string; name: string; genre: string; timing: string; milestones: number; trials: number;
  intro: string; controls: string; logo: boolean; shots: number; best: { agent: string; mode: string };
  case: string; replay: Step[];
};
export type Mode = 'live' | 'frozen';
export type Author = { name: string; inst: string; equal: boolean; corr: boolean };

export const data = raw as unknown as {
  games: Game[]; models: string[]; scores: Record<string, Record<Mode, Record<string, number | null>>>;
  abstract: string; authors: Author[]; latency: Record<string, number>;
};

export const img = (p: string) => `${import.meta.env.BASE_URL}img/${p}`;

/** Best score of any agent in any mode for one game. */
export function best(slug: string): { model: string; mode: Mode; score: number } {
  let out = { model: '', mode: 'live' as Mode, score: -1 };
  for (const m of data.models)
    for (const mode of ['live', 'frozen'] as Mode[]) {
      const s = data.scores[m][mode][slug];
      if (s != null && s > out.score) out = { model: m, mode, score: s };
    }
  return out;
}

/** An agent action written as a short sentence. */
export function say(a: Action): string {
  const key = (k: string) => (k.length === 1 ? k.toUpperCase() : k[0].toUpperCase() + k.slice(1));
  const where = (x?: number, y?: number) => (x == null || y == null ? '' : ` at ${Math.round(x * 100)}% across, ${Math.round(y * 100)}% down`);
  switch (a.type) {
    case 'control': {
      const keys = (a.keys ?? []).map(key);
      const btn = (a.buttons ?? []).map(b => `${b} mouse`);
      const look = a.dx || a.dy ? ` and turns the view ${Math.abs(a.dx ?? 0) >= Math.abs(a.dy ?? 0) ? ((a.dx ?? 0) > 0 ? 'right' : 'left') : ((a.dy ?? 0) > 0 ? 'down' : 'up')}` : '';
      const held = [...keys, ...btn];
      return held.length ? `Holds ${held.join(' + ')} for ${a.duration ?? 0} s${look}.` : `Turns the view${look.replace(' and turns the view', '')} for ${a.duration ?? 0} s.`;
    }
    case 'pointer': return a.button ? `Clicks ${a.button}${where(a.x, a.y)}.` : `Moves the mouse${where(a.x, a.y)}.`;
    case 'drag': return `Drags from${where(a.x, a.y)} to${where(a.to_x, a.to_y)}.`;
    case 'wait': return `Waits ${a.seconds ?? 0} s.`;
    case 'type': return `Types “${a.text ?? ''}”.`;
    case 'key': return `Presses ${(a.keys ?? []).map(key).join(' + ')}.`;
    default: return `${a.type}.`;
  }
}
