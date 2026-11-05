#!/usr/bin/env python3
"""
HUD telemetry panel for the 0xayushM profile README.

Replaces the hosted widgets (github-readme-stats, streak-stats, activity graph)
with one SVG generated inside this repo's own GitHub Action. Standard library only.

Usage:  GH_TOKEN=... GH_LOGIN=0xayushM python3 scripts/telemetry.py dist/telemetry.svg
        python3 scripts/telemetry.py out.svg --mock     (renders sample data, no network)
"""
import datetime as dt
import json
import math
import os
import random
import sys
import urllib.request

API = "https://api.github.com/graphql"
MONO = "'JetBrains Mono','SF Mono','Cascadia Code',Menlo,Consolas,'DejaVu Sans Mono',monospace"
BG0, BG1 = "#03060c", "#071626"
CY, CY2, AMB, MAG, OKG = "#00e5ff", "#7cf3ff", "#ffb547", "#ff2bd6", "#3dffa8"
TXT, DIM = "#d7f6ff", "#6f8ea3"


# ----------------------------------------------------------------------------- data
def gql(token, query, variables):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "hud-telemetry"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    if out.get("errors"):
        raise RuntimeError(json.dumps(out["errors"], indent=2))
    return out["data"]


Q_PROFILE = """
query($login: String!, $after: String) {
  user(login: $login) {
    login
    createdAt
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(first: 100, after: $after, ownerAffiliations: [OWNER], isFork: false,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}"""

Q_YEAR = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(token, login):
    stars, langs, repo_count, after = 0, {}, 0, None
    while True:
        u = gql(token, Q_PROFILE, {"login": login, "after": after})["user"]
        repos = u["repositories"]
        repo_count = repos["totalCount"]
        for n in repos["nodes"]:
            stars += n["stargazerCount"]
            for e in n["languages"]["edges"]:
                name = e["node"]["name"]
                c = langs.setdefault(name, {"size": 0, "color": e["node"]["color"] or CY})
                c["size"] += e["size"]
        if not repos["pageInfo"]["hasNextPage"]:
            break
        after = repos["pageInfo"]["endCursor"]

    now = dt.datetime.now(dt.timezone.utc)
    start = dt.datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
    days, commits = {}, 0
    while start < now:
        end = min(start + dt.timedelta(days=365), now)
        cc = gql(token, Q_YEAR, {"login": login, "from": iso(start), "to": iso(end)})["user"]["contributionsCollection"]
        commits += cc["totalCommitContributions"]
        for w in cc["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
        start = end

    return {
        "login": u["login"],
        "since": u["createdAt"][:4],
        "followers": u["followers"]["totalCount"],
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "repos": repo_count,
        "stars": stars,
        "commits": commits,
        "langs": langs,
        "days": days,
        "now": now,
    }


def mock():
    now = dt.datetime.now(dt.timezone.utc)
    random.seed(7)
    days = {}
    for i in range(700):
        d = (now - dt.timedelta(days=i)).date().isoformat()
        days[d] = 0 if random.random() < 0.25 else random.randint(1, 14)
    for i in range(9):
        days[(now - dt.timedelta(days=i)).date().isoformat()] = random.randint(2, 12)
    return {"login": "0xayushM", "since": "2020", "followers": 48, "prs": 63, "issues": 21, "repos": 37,
            "stars": 112, "commits": 2381,
            "langs": {"TypeScript": {"size": 900, "color": "#3178c6"}, "JavaScript": {"size": 420, "color": "#f1e05a"},
                      "Python": {"size": 260, "color": "#3572A5"}, "CSS": {"size": 140, "color": "#563d7c"},
                      "HTML": {"size": 90, "color": "#e34c26"}, "Solidity": {"size": 40, "color": "#AA6746"},
                      "Shell": {"size": 20, "color": "#89e051"}},
            "days": days, "now": now}


# ----------------------------------------------------------------------------- stats
def streaks(days, today):
    ordered = sorted(days.items())
    longest = run = 0
    for _, c in ordered:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    # current: count back from today; a zero today doesn't break it yet
    cur, d = 0, today
    if days.get(d.isoformat(), 0) == 0:
        d -= dt.timedelta(days=1)
    while days.get(d.isoformat(), 0) > 0:
        cur += 1
        d -= dt.timedelta(days=1)
    return cur, longest


def fmt(n):
    if n >= 10000:
        return f"{n/1000:.1f}k".replace(".0k", "k")
    return f"{n:,}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ----------------------------------------------------------------------------- render
def render(data):
    W, H = 1200, 590
    today = data["now"].date()
    total = sum(data["days"].values())
    cur, longest = streaks(data["days"], today)

    # --- tiles
    tiles = [("CONTRIBUTIONS", total, f"since {data['since']}"), ("COMMITS", data["commits"], "all time"),
             ("PULL REQUESTS", data["prs"], "opened"), ("ISSUES", data["issues"], "opened"),
             ("STARS EARNED", data["stars"], "own repos"), ("REPOSITORIES", data["repos"], "owned, non-fork")]
    tw, th, tx0, ty0, tg = 184, 86, 30, 84, 14
    tile_svg = []
    for i, (lab, val, sub) in enumerate(tiles):
        x = tx0 + (i % 2) * (tw + tg)
        y = ty0 + (i // 2) * (th + tg)
        d = 0.15 + i * 0.12
        tile_svg.append(f"""
  <g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{d:.2f}s" dur=".4s" fill="freeze"/>
    <path d="M{x+12} {y}H{x+tw}V{y+th-12}L{x+tw-12} {y+th}H{x}V{y+12}Z" fill="#06141f" stroke="{CY}" stroke-opacity=".35"/>
    <path d="M{x} {y+12}V{y}H{x+12}" fill="none" stroke="{CY}" stroke-width="2"/>
    <text x="{x+16}" y="{y+26}" fill="{AMB}" letter-spacing="2" style="font-size:10.5px">{lab}</text>
    <text x="{x+16}" y="{y+60}" fill="#ffffff" font-weight="800" letter-spacing="1" filter="url(#tneon)" style="font-size:29px">{fmt(val)}</text>
    <text x="{x+16}" y="{y+77}" fill="{DIM}" style="font-size:10.5px">{esc(sub)}</text>
  </g>""")
    tile_svg = "".join(tile_svg)

    # --- streak ring
    rx, ry, rr = 600, 220, 100
    frac = 0 if longest == 0 else cur / longest
    circ = 2 * math.pi * rr
    ticks = "".join(
        f'<line x1="{rx + (rr+14)*math.cos(math.radians(a)):.1f}" y1="{ry + (rr+14)*math.sin(math.radians(a)):.1f}" '
        f'x2="{rx + (rr+(22 if a % 30 == 0 else 18))*math.cos(math.radians(a)):.1f}" y2="{ry + (rr+(22 if a % 30 == 0 else 18))*math.sin(math.radians(a)):.1f}"/>'
        for a in range(0, 360, 6))
    ring = f"""
  <g stroke="{CY}" stroke-opacity=".45" stroke-width="1.2">{ticks}
    <animateTransform attributeName="transform" type="rotate" from="0 {rx} {ry}" to="360 {rx} {ry}" dur="80s" repeatCount="indefinite"/>
  </g>
  <circle cx="{rx}" cy="{ry}" r="{rr}" fill="none" stroke="{CY}" stroke-opacity=".12" stroke-width="12"/>
  <circle cx="{rx}" cy="{ry}" r="{rr}" fill="none" stroke="{AMB}" stroke-width="12" stroke-linecap="round"
          stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}" transform="rotate(-90 {rx} {ry})" filter="url(#tneon)">
    <animate attributeName="stroke-dashoffset" from="{circ:.1f}" to="{circ*(1-frac):.1f}" begin=".4s" dur="1.6s" fill="freeze"/>
  </circle>
  <circle cx="{rx}" cy="{ry}" r="{rr-24}" fill="none" stroke="{CY}" stroke-opacity=".35" stroke-dasharray="3 7">
    <animateTransform attributeName="transform" type="rotate" from="360 {rx} {ry}" to="0 {rx} {ry}" dur="20s" repeatCount="indefinite"/>
  </circle>
  <text x="{rx}" y="{ry-34}" text-anchor="middle" fill="{AMB}" letter-spacing="3" style="font-size:10.5px">CURRENT STREAK</text>
  <text x="{rx}" y="{ry+22}" text-anchor="middle" fill="#ffffff" font-weight="800" filter="url(#tneon)" style="font-size:52px">{cur}</text>
  <text x="{rx}" y="{ry+44}" text-anchor="middle" fill="{DIM}" letter-spacing="3" style="font-size:10.5px">DAY{'S' if cur != 1 else ''}</text>
  <text x="{rx}" y="{ry+rr+50}" text-anchor="middle" fill="{TXT}" letter-spacing="2" style="font-size:12px">LONGEST <tspan fill="{CY}" font-weight="700">{longest}</tspan> DAYS · {fmt(total)} TOTAL</text>"""

    # --- languages
    langs = sorted(data["langs"].items(), key=lambda kv: -kv[1]["size"])[:6]
    lsum = sum(v["size"] for _, v in langs) or 1
    lx, ly, lw = 790, 104, 380
    lang_svg = [f'<text x="{lx}" y="{ly-26}" fill="{CY}" letter-spacing="3" style="font-size:12px">TOP LANGUAGES</text>',
                f'<text x="{lx+lw}" y="{ly-26}" text-anchor="end" fill="{DIM}" letter-spacing="2" style="font-size:10.5px">BY CODE SIZE</text>',
                f'<line x1="{lx}" y1="{ly-16}" x2="{lx+lw}" y2="{ly-16}" stroke="{CY}" stroke-opacity=".25"/>']
    if not langs:
        lang_svg.append(f'<text x="{lx}" y="{ly+20}" fill="{DIM}" style="font-size:12px">no public code yet</text>')
    for i, (name, v) in enumerate(langs):
        y = ly + i * 40
        pct = v["size"] / lsum
        d = 0.3 + i * 0.12
        lang_svg.append(f"""
  <g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{d:.2f}s" dur=".4s" fill="freeze"/>
    <rect x="{lx}" y="{y-9}" width="8" height="8" fill="{v['color']}"/>
    <text x="{lx+16}" y="{y}" fill="#ffffff" font-weight="700" letter-spacing="1.5" style="font-size:13px">{esc(name.upper())}</text>
    <text x="{lx+lw}" y="{y}" text-anchor="end" fill="{CY}" style="font-size:12px">{pct*100:.1f}%</text>
    <rect x="{lx}" y="{y+8}" width="{lw}" height="5" fill="{CY}" fill-opacity=".1"/>
    <rect x="{lx}" y="{y+8}" width="0" height="5" fill="{CY}" filter="url(#tneon)">
      <animate attributeName="width" from="0" to="{lw*pct:.1f}" begin="{d+0.2:.2f}s" dur="1.1s" fill="freeze"/>
    </rect>
  </g>""")
    lang_svg = "".join(lang_svg)

    # --- 31-day activity
    span = [(today - dt.timedelta(days=30 - i)) for i in range(31)]
    vals = [data["days"].get(d.isoformat(), 0) for d in span]
    vmax = max(vals) or 1
    cx0, cx1, cyb, ch = 70, 1150, 548, 120
    pts = [(cx0 + i * (cx1 - cx0) / 30, cyb - v / vmax * ch) for i, v in enumerate(vals)]
    line = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    area = line + f" L{cx1} {cyb} L{cx0} {cyb}Z"
    grid = "".join(f'<line x1="{cx0}" y1="{cyb - ch*k/4:.1f}" x2="{cx1}" y2="{cyb - ch*k/4:.1f}" stroke="{CY}" stroke-opacity="{.25 if k == 0 else .08}"/>' for k in range(5))
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{3.2 if v else 2}" fill="{AMB if v == vmax and v else (CY if v else DIM)}" opacity="0">'
                   f'<animate attributeName="opacity" from="0" to="1" begin="{0.6 + i*0.04:.2f}s" dur=".2s" fill="freeze"/></circle>'
                   for i, ((x, y), v) in enumerate(zip(pts, vals)))
    xl = "".join(f'<text x="{pts[i][0]:.1f}" y="{cyb+18}" text-anchor="middle" fill="{DIM}" style="font-size:10px">{span[i].strftime("%d %b").upper()}</text>'
                 for i in range(0, 31, 5))
    chart = f"""
  <text x="30" y="{cyb-ch-30}" fill="{CY}" letter-spacing="3" style="font-size:12px">SIGNAL ACTIVITY · LAST 31 DAYS</text>
  <text x="1170" y="{cyb-ch-30}" text-anchor="end" fill="{DIM}" letter-spacing="2" style="font-size:10.5px">{sum(vals)} CONTRIBUTIONS · PEAK {max(vals)}</text>
  {grid}
  <text x="{cx0-12}" y="{cyb-ch+4}" text-anchor="end" fill="{DIM}" style="font-size:10px">{vmax}</text>
  <text x="{cx0-12}" y="{cyb+4}" text-anchor="end" fill="{DIM}" style="font-size:10px">0</text>
  <path d="{area}" fill="url(#tarea)" opacity="0"><animate attributeName="opacity" from="0" to="1" begin="1.2s" dur=".8s" fill="freeze"/></path>
  <path d="{line}" fill="none" stroke="{CY}" stroke-width="2.2" stroke-linejoin="round" filter="url(#tneon)"
        pathLength="1" stroke-dasharray="1" stroke-dashoffset="1">
    <animate attributeName="stroke-dashoffset" from="1" to="0" begin=".5s" dur="1.6s" fill="freeze"/>
  </path>
  {dots}{xl}"""

    stamp = data["now"].strftime("%d %b %Y · %H:%M UTC").upper()

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub telemetry for {esc(data['login'])}">
<title>GitHub telemetry: {fmt(total)} contributions, {cur}-day streak</title>
<defs>
  <linearGradient id="tbg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG0}"/><stop offset="1" stop-color="{BG1}"/></linearGradient>
  <pattern id="tgrid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="{CY}" stroke-opacity=".06"/></pattern>
  <pattern id="tlines" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" fill-opacity=".35"/></pattern>
  <linearGradient id="tscan" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CY}" stop-opacity="0"/><stop offset=".9" stop-color="{CY}" stop-opacity=".16"/><stop offset="1" stop-color="{CY2}" stop-opacity=".6"/></linearGradient>
  <linearGradient id="tarea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{CY}" stop-opacity=".35"/><stop offset="1" stop-color="{CY}" stop-opacity="0"/></linearGradient>
  <filter id="tneon" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="2.8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <clipPath id="tclip"><rect width="{W}" height="{H}" rx="16"/></clipPath>
</defs>
<style> text {{ font-family: {MONO}; }} .blink {{ animation: bl 1s infinite steps(1); }} @keyframes bl {{ 50% {{ opacity:0; }} }} </style>
<g clip-path="url(#tclip)">
  <rect width="{W}" height="{H}" rx="16" fill="url(#tbg)"/>
  <rect width="{W}" height="{H}" fill="url(#tgrid)"/>
  <text x="30" y="46" fill="{CY}" letter-spacing="3" style="font-size:13px"><tspan class="blink" fill="{OKG}">● </tspan>LIVE TELEMETRY // @{esc(data['login'])}</text>
  <text x="1170" y="46" text-anchor="end" fill="{DIM}" letter-spacing="2" style="font-size:11px">SYNCED {stamp}</text>
  <line x1="30" y1="60" x2="1170" y2="60" stroke="{CY}" stroke-opacity=".2"/>
  {tile_svg}
  {ring}
  {lang_svg}
  {chart}
  <rect y="-140" width="{W}" height="140" fill="url(#tscan)"><animate attributeName="y" values="-140;{H}" dur="8s" repeatCount="indefinite"/></rect>
  <rect width="{W}" height="{H}" fill="url(#tlines)" opacity=".5"/>
  <rect x=".75" y=".75" width="{W-1.5}" height="{H-1.5}" rx="16" fill="none" stroke="{CY}" stroke-opacity=".28" stroke-width="1.5"/>
  <g stroke="{CY}" stroke-width="2" fill="none" opacity=".9">
    <path d="M10 36V10H36"/><path d="M{W-36} 10H{W-10}V36"/><path d="M10 {H-36}V{H-10}H36"/><path d="M{W-36} {H-10}H{W-10}V{H-36}"/>
  </g>
</g>
</svg>
"""


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "telemetry.svg"
    if "--mock" in sys.argv:
        data = mock()
    else:
        token, login = os.environ.get("GH_TOKEN"), os.environ.get("GH_LOGIN")
        if not token or not login:
            sys.exit("GH_TOKEN and GH_LOGIN are required (or pass --mock)")
        data = fetch(token, login)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write(render(data))
    print(f"wrote {out}: {sum(data['days'].values())} contributions, {len(data['langs'])} languages")


if __name__ == "__main__":
    main()
