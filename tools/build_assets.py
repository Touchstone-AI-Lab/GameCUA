# Build the site's images and data (public/img, src/data.json) from the paper sources and the trial data
# downloaded from the Hugging Face dataset. Usage: python tools/build_assets.py <paper_dir> <data_dir>
import json, os, re, subprocess, sys, shutil, glob
from PIL import Image

PAPER, DATA = sys.argv[1], sys.argv[2]
SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = f'{SITE}/public/img'

GAMES = [  # slug, display name, paper short name (results table order)
    ('dont-starve', "Don't Starve"), ('oxygen-not-included', 'Oxygen Not Included'), ('art-of-rally', 'art of rally'),
    ('the-binding-of-isaac-rebirth', 'The Binding of Isaac'), ('papers-please', 'Papers, Please'),
    ('left-4-dead-2', 'Left 4 Dead 2'), ('stardew-valley', 'Stardew Valley'), ('untitled-goose-game', 'Untitled Goose Game'),
    ('factorio', 'Factorio'), ('hollow-knight-silksong', 'Hollow Knight: Silksong'), ('peak', 'PEAK'),
    ('slay-the-spire', 'Slay the Spire'), ('civilization-vi', 'Civilization VI'), ('baba-is-you', 'Baba Is You'),
    ('understand', 'Understand')]
MODELS = ['GPT-6-Astra', 'DeepSeek-Flash', 'Opus 5.5', 'Kimi K3.1 Pro', 'Grok 4.7', 'Jev 1.14.0']
AGENT_DIR = {'gpt-6-astra': 'GPT-6-Astra', 'deepseek-v41-flash-thinking': 'DeepSeek-Flash', 'claude-opus-5-5': 'Opus 5.5'}


def webp(src, dst, width=None, q=78, im=None):
    """Save an image as WebP, optionally resized to a target width."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im = im or Image.open(src)
    if im.mode not in ('RGB', 'RGBA'):
        im = im.convert('RGBA')
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(dst, 'WEBP', quality=q, method=6)


def tex_plain(s):
    """Strip the few LaTeX constructs used in the paper's game texts."""
    s = re.sub(r'\\benchmark(\{\})?', 'GameCUA', s)
    s = re.sub(r'\\par\\smallskip|\\par\b', ' ', s)
    s = re.sub(r'\\(emph|textit|textbf|texttt)\{([^}]*)\}', r'\2', s)
    s = s.replace('~', ' ').replace('\\,', ' ').replace('---', '—').replace('--', '–').replace("\\'", "'")
    s = re.sub(r'\$\\times\$', '×', s)
    s = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', s)
    return re.sub(r'\s+', ' ', s.replace('\\', '')).strip()


def scores():
    """Parse the main results table: score[model][mode][game] (None where a mode does not apply)."""
    src = open(f'{PAPER}/sec_arxiv/4_protocol.tex').read()
    order = [g for g, _ in GAMES]
    halves = [order[:9], order[9:11] + ['avg-rt'] + order[11:15] + ['avg-tb']]
    out = {m: {'live': {}, 'frozen': {}} for m in MODELS}
    for half, block in zip(halves, src.split(r'\begin{tabularx}')[1:3]):
        model = None
        for line in block.splitlines():
            m = re.search(r'\\textbf\{([^}]*)\}\}\s*$', line)
            if m and m.group(1) in MODELS:
                model = m.group(1)
            m = re.match(r'\s*&\s*(Live|Frozen)\s*&(.*)\\\\', line)
            if m and model:
                cells = [re.sub(r'\\cellcolor\[HTML\]\{\w+\}|\\textbf\{|\}', '', c).strip() for c in m.group(2).split('&')]
                for g, c in zip(half, cells):
                    out[model][m.group(1).lower()][g] = None if c == '--' else float(c)
    return out


def games_meta():
    rows = {}
    for line in open(f'{PAPER}/sec_arxiv/appx/gen/games_table.tex'):
        c = [x.strip() for x in line.rstrip().rstrip('\\').split('&')]
        if len(c) == 7:
            rows[c[0]] = {'genre': c[1], 'timing': c[2], 'milestones': int(c[5]), 'trials': int(c[6])}
    pages = open(f'{PAPER}/sec_arxiv/appx/gen/game_pages.tex').read()
    intro = {}
    for part in pages.split(r'\subsection{')[1:]:
        name = part.split('}')[0]
        m = re.search(r'\\begin\{gcbox\}\{Game introduction\}(.*?)\\end\{gcbox\}', part, re.S)
        c = re.search(r'\\begin\{gcbox\}\{Controls\}(.*?)\\end\{gcbox\}', part, re.S)
        intro[tex_plain(name)] = (tex_plain(m.group(1)) if m else '', tex_plain(c.group(1)) if c else '')
    cases = {}
    for m in re.finditer(r'\\paragraph\{([^}]*)\.\}(.*?)\n', open(f'{PAPER}/sec_arxiv/appx/H_cases.tex').read()):
        cases[tex_plain(m.group(1)).replace('Civilization VI', 'Civilization VI')] = tex_plain(m.group(2))
    return rows, intro, cases


def paper_text():
    """Abstract, author list (name, institution, marks) and per-agent median latency from the paper."""
    ab = open(f'{PAPER}/sec_arxiv/0_abstract.tex').read().split('\n\\small\n', 1)[1].split(r'\end{abstract}')[0]
    main = open(f'{PAPER}/main.tex').read()
    inst = {k: tex_plain(re.sub(r'\\textcolor\{blue\}\{(.*)\}', r'\1', v)) for k, v in re.findall(r'\\cardaffil\{(\w+)\}\{(.*)\}', main)}
    authors = []
    for k, mark, name in re.findall(r'\\carda\{(\w+)\}\{((?:[^{}]|\{[^}]*\})*)\}\{(.*?)\}%', main):
        name = tex_plain(re.sub(r'\\textcolor\{blue\}\{(.*)\}', r'\1', name).replace('~', ' '))
        authors.append({'name': name, 'inst': inst.get(k, ''), 'equal': '*' in mark, 'corr': 'ding' in mark})
    lat = {}
    for line in open(f'{PAPER}/sec_arxiv/appx/gen/model_table.tex'):
        c = [x.strip() for x in line.split('&')]
        if len(c) > 4:
            lat[c[0]] = float(c[3])
    return tex_plain(ab), authors, lat


def main():
    for d in ('poster', 'hero', 'logo', 'shot', 'replay', 'err'):
        shutil.rmtree(f'{PUB}/{d}', ignore_errors=True)
    rows, intro, cases = games_meta()
    picked = json.load(open(f'{DATA}/picked.json'))
    replays = json.load(open(f'{DATA}/replays.json'))
    games = []
    for slug, name in GAMES:
        p = f'{DATA}/posters/{slug}'
        webp(f'{p}.library_600x900_2x.jpg', f'{PUB}/poster/{slug}.webp', 600, 82)
        webp(f'{p}.library_hero.jpg', f'{PUB}/hero/{slug}.webp', 1600, 74)
        has_logo = os.path.exists(f'{p}.logo.png')
        if has_logo:
            webp(f'{p}.logo.png', f'{PUB}/logo/{slug}.webp', 640, 90)
        shots = [s for s in picked[slug]['picked'] if s.endswith('.png')]
        for i, s in enumerate(shots):
            webp(f'{DATA}/{s}', f'{PUB}/shot/{slug}/{i:02d}.webp', 960, 72)
        steps = []
        for i, r in enumerate(replays.get(slug, [])):
            webp(f"{DATA}/{r['img']}", f'{PUB}/replay/{slug}/{i:02d}.webp', 1100, 74)
            steps.append({**{k: r[k] for k in ('observation', 'hypothesis', 'action')},
                          'decision': int(os.path.basename(r['img']).split('_')[0])})
        agent, mode = picked[slug]['trial'].split('/')
        meta = rows.get(name, rows.get(name.replace('The Binding of Isaac', 'The Binding of Isaac'), {}))
        gi, gc = intro.get(name, ('', ''))
        games.append({'slug': slug, 'name': name, **meta, 'intro': gi, 'controls': gc, 'logo': has_logo,
                      'shots': len(shots), 'best': {'agent': AGENT_DIR.get(agent, agent), 'mode': mode},
                      'case': cases.get(name, cases.get(name.split(':')[0], '')), 'replay': steps})
    errs = []
    for f, cat in [('err_plan_baba', 'plan'), ('err_vis_isaac', 'vis'), ('err_know_peak', 'know'),
                   ('err_act_oni', 'act'), ('err_rt_rally', 'rt')]:
        tmp = f'{SITE}/.tmp_{f}'
        subprocess.run(['pdftoppm', '-r', '160', '-png', '-singlefile', f'{PAPER}/figures/appx/{f}.pdf', tmp], check=True)
        webp(f'{tmp}.png', f'{PUB}/err/{cat}.webp', 1400, 80)
        os.remove(f'{tmp}.png')
        errs.append(cat)
    abstract, authors, lat = paper_text()
    json.dump({'games': games, 'models': MODELS, 'scores': scores(), 'abstract': abstract, 'authors': authors,
               'latency': lat},
              open(f'{SITE}/src/data.json', 'w'), indent=1, ensure_ascii=False)
    total = sum(os.path.getsize(x) for x in glob.glob(f'{PUB}/**/*', recursive=True) if os.path.isfile(x))
    print(len(games), 'games;', round(total / 1e6, 1), 'MB of images')


main()
