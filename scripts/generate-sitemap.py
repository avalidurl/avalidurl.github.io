#!/usr/bin/env python3
"""Rebuild index.html as a browsable sitemap of gokhanturhan.com.

Fetches the live XML sitemap (and journal RSS) with curl and a browser-like
User-Agent — gokhanturhan.com blocks the default python-urllib UA.

Usage: python3 scripts/generate-sitemap.py
       (run from the repo root, or from anywhere; paths are relative to this file)
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
SITE = "https://gokhanturhan.com"
SITE_HOST = "gokhanturhan.com"
SITEMAP_INDEX = f"{SITE}/sitemap-index.xml"
RSS_URL = f"{SITE}/rss.xml"
SEARCH_URL = f"{SITE}/search.json"
SM_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def is_site_host(netloc: str) -> bool:
    host = netloc.split("@")[-1].split(":")[0].strip().lower().rstrip(".")
    return host == SITE_HOST or host.endswith("." + SITE_HOST)

FEATURED = [
    "curb",
    "ishtar",
    "numetal",
    "gokhan-vc",
    "heartprefs",
    "tickerline",
    "turkish-art-blob",
    "agentbounty",
    "launch",
    "ubu",
    "sp100-capex-dashboard",
    "market-cap-tracker",
    "ai-ipo",
    "ethereum-doomsday",
]

PRODUCT_NAMES = {
    "numetal": "Numetal",
    "ishtar": "Ishtar",
    "heartprefs": "HeartPrefs",
    "curb": "CURB",
    "launch": "Launch",
    "ubu": "UBU \u00b7 CLINAMEN",
    "ccru": "CCRU archive",
    "reclaim": "Reclaim",
    "plaintext": "plaintext",
    "accumulator": "Accumulator",
    "rebase": "REBASE",
    "apex": "APEX PROTOCOL",
    "booster": "BOOSTER",
    "coins": "The Token Estate",
    "jesus": "Personal Jesus",
    "llmcraft": "LLMCraft",
    "llmlivesmatter": "LLM LIVES MATTER",
    "gokhan-vc": "G\u00f6khan Ventures",
    "agentbounty": "AgentBounty",
    "tickerline": "tickerline",
    "market-cap-tracker": "Market Cap Tracker",
    "sp100-capex-dashboard": "S&P 100 CapEx Dashboard",
    "greek-alphabet-anki": "Greek Alphabet Anki",
    "biases-fallacies-lab": "Biases & Fallacies Lab",
    "turkish-art-blob": "Turkish Art Blob",
    "ethereum-doomsday": "Ethereum Doomsday Tracker",
    "ai-ipo": "AI IPO forecasts",
    "belief-systems": "Trust Tax Belief Systems \u00b7 $BELIEF",
    "clank-tape": "Clank Tape",
    "clankdog": "Clank Dog \u00b7 $CLANKDOG",
    "foreguild-fao-plan": "Foreguild FAO revenue plan",
    "hypersitition": "hypersitition",
    "lectotype": "Lectotype",
    "onbots": "Onchain Agent Bot Services \u00b7 $ONBOTS",
    "tape-exchange": "The Tape Exchange \u00b7 $TAPEX",
}

# Paths stored without a trailing slash, except "/".
TITLE_MAP = {
    "/": "Home",
    "/about": "About",
    "/about/cite-a-page": "Cite or link a page",
    "/about/colophon": "Colophon",
    "/about/contact": "Get in touch",
    "/about/design-notes": "Design notes",
    "/about/feeds-and-files": "Feeds and files",
    "/about/find-an-old-project": "Find an old project",
    "/about/first-agent-read": "Your first agent read",
    "/about/follow-by-rss": "Follow by RSS",
    "/about/get-the-cv": "Get the CV",
    "/about/how-products-are-organised": "How the products are organised",
    "/about/newsletter-reference": "Newsletter",
    "/about/read-the-legal-pages": "Read the legal pages",
    "/about/read-the-site": "Read the site in ten minutes",
    "/about/site-sections": "Site sections",
    "/about/subscribe": "Subscribe to the journal by email",
    "/about/unsubscribe": "Unsubscribe from the newsletter",
    "/about/what-this-site-is": "What this site is",
    "/about/why-addresses-moved": "Why addresses moved",
    "/cv": "CV",
    "/links": "Links",
    "/newsletter": "Newsletter",
    "/consulting": "Consulting",
    "/products": "Products",
    "/product-drafts": "Product drafts",
    "/writing": "Writing",
    "/journal": "Journal",
    "/privacy": "Privacy",
    "/disclaimer": "Disclaimer",
    "/agents": "For agents",
    "/raises": "Raises",
    "/offline": "Offline",
    "/moved": "Moved",
    "/tools": "Tools",
    "/lists": "Lists",
    "/art": "Art",
    "/haleanbar": "Hale Anbar",
    "/archive": "Archive",
    "/archive/tags": "Tags",
    "/publishing": "Publishing",
    "/publishing/academic": "Academic",
    "/publishing/academic/on-the-hyperstitional-implications-of-memes-as-digital": (
        "On the Hyperstitional Implications of Memes as Digital Objects in Turkey"
    ),
    "/publishing/academic/the-importance-and-function-of-media-laboratories-for": (
        "The Importance and Function of Media Laboratories for the Preservation "
        "of Works of Digital and Electronic Literature"
    ),
    "/publishing/ebooks": "E-books",
    "/publishing/ebooks/an-essay-concerning-the-inbox": "An Essay Concerning the Inbox",
    "/publishing/ebooks/an-essay-concerning-the-inbox/read": "An Essay Concerning the Inbox \u2014 Read",
    "/publishing/ebooks/gradient-descent-into-chaotic-happiness": "Gradient Descent into Chaotic Happiness",
    "/publishing/ebooks/gradient-descent-into-chaotic-happiness/read": (
        "Gradient Descent into Chaotic Happiness \u2014 Read"
    ),
    "/publishing/ebooks/the-guy-with-compute": "The Guy with Compute",
    "/publishing/ebooks/the-guy-with-compute/read": "The Guy with Compute \u2014 Read",
    "/publishing/experimental": "Experimental",
    "/publishing/experimental/casette": "CASSETTE",
    "/ishtar/dashboard": "The Floor",
    "/ishtar/talk": "Talk to Ishtar",
    "/ishtar/window": "The Window",
    "/ishtar/heartbench": "HeartBench",
    "/ishtar/heartbench/scenarios": "Scenarios",
    "/ishtar/play": "Play",
    "/ishtar/pricing": "Pricing",
    "/ishtar/deck": "Deck",
    "/ishtar/newsletter": "Newsletter",
    "/ishtar/docs": "Docs",
    "/ishtar/docs/agents": "Agents",
    "/ishtar/docs/agents/admission-and-chaperone": "Admission and chaperone",
    "/ishtar/docs/agents/api-reference": "API reference",
    "/ishtar/docs/agents/boards": "Boards",
    "/ishtar/docs/agents/heart-file-spec": "Heart file spec",
    "/ishtar/docs/agents/matching-and-courtship": "Matching and courtship",
    "/ishtar/docs/agents/overview": "Overview",
    "/ishtar/docs/agents/paid-compatibility-report": "Paid compatibility report",
    "/ishtar/docs/agents/pricing-and-limits": "Pricing and limits",
    "/ishtar/docs/agents/quickstart": "Quickstart",
    "/ishtar/docs/agents/skill": "Skill",
    "/ishtar/docs/heartbench": "HeartBench docs",
    "/ishtar/docs/humans": "For humans",
    "/ishtar/docs/humans/faq": "FAQ",
    "/ishtar/docs/humans/getting-an-intro": "Getting an intro",
    "/ishtar/docs/humans/how-it-works": "How it works",
    "/ishtar/docs/humans/identity-and-safety": "Identity and safety",
    "/ishtar/docs/humans/talk-to-ishtar": "Talk to Ishtar",
    "/ishtar/docs/ishtar-the-agent": "Ishtar the agent",
    "/ishtar/docs/numetal": "Numetal",
    "/ishtar/legal/age-verification": "Age verification",
    "/ishtar/legal/csae-standards": "CSAE standards",
    "/ishtar/legal/geo-and-data": "Geo and data",
    "/ishtar/legal/moderation": "Moderation",
    "/ishtar/legal/privacy-policy": "Privacy policy",
    "/ishtar/legal/terms-of-service": "Terms of service",
    "/curb/deck": "Deck",
    "/curb/docs": "Docs",
    "/curb/fees": "Fees",
    "/curb/harness": "Harness",
    "/curb/harness/agents": "Harness agents",
    "/curb/install": "Install",
    "/curb/newsletter": "Newsletter",
    "/curb/docs/explanation": "Explanation",
    "/curb/docs/explanation/fees": "Fees",
    "/curb/docs/explanation/harness-agents": "Harness agents",
    "/curb/docs/explanation/single-payee-x402": "Single-payee x402",
    "/curb/docs/explanation/what-curb-is": "What CURB is",
    "/curb/docs/explanation/why-no-keys": "Why no keys",
    "/curb/docs/how-to": "How-to",
    "/curb/docs/how-to/install-mcp": "Install MCP",
    "/curb/docs/how-to/install-skill": "Install skill",
    "/curb/docs/how-to/pay-match": "Pay a match",
    "/curb/docs/how-to/post-intent": "Post an intent",
    "/curb/docs/how-to/post-offer": "Post an offer",
    "/curb/docs/how-to/use-live-harness": "Use the live harness",
    "/curb/docs/reference": "Reference",
    "/curb/docs/reference/api": "API",
    "/curb/docs/reference/discovery": "Discovery",
    "/curb/docs/reference/errors": "Errors",
    "/curb/docs/reference/mcp-tools": "MCP tools",
    "/curb/docs/reference/openapi": "OpenAPI",
    "/curb/docs/reference/skill": "Skill",
    "/curb/docs/tutorials": "Tutorials",
    "/curb/docs/tutorials/first-swap": "First swap",
    "/curb/docs/tutorials/sell-capacity": "Sell capacity",
    "/curb/legal/privacy": "Privacy",
    "/curb/legal/terms": "Terms",
    "/numetal/airdrops": "Airdrops",
    "/numetal/decks": "Decks",
    "/numetal/fees": "Fees",
    "/numetal/newsletter": "Newsletter",
    "/numetal/status": "Status board",
    "/numetal/legal/cookies": "Cookies",
    "/numetal/legal/privacy": "Privacy",
    "/numetal/legal/terms": "Terms",
    "/gokhan-vc/api": "feedhub",
    "/gokhan-vc/newsletter": "Newsletter",
    "/gokhan-vc/projects": "Projects",
    "/gokhan-vc/legal/cookies": "Cookies",
    "/gokhan-vc/legal/privacy": "Privacy",
    "/gokhan-vc/legal/terms": "Terms",
    "/heartprefs/governance": "Governance",
    "/heartprefs/sdk": "SDK",
    "/heartprefs/spec": "Spec",
    "/heartprefs/standards": "Standards",
    "/launch/app": "App",
    "/launch/source": "Source",
    "/ubu/ledger": "Ledger",
    "/ubu/reader": "Reader",
    "/turkish-art-blob/tr": "T\u00fcrk\u00e7e",
    "/agentbounty/airdrops": "Airdrops",
    "/agentbounty/blog": "Blog",
    "/agentbounty/bounties": "Bounties",
    "/agentbounty/claim": "Claim",
    "/agentbounty/community": "Community",
    "/agentbounty/compare": "Compare",
    "/agentbounty/contact": "Contact",
    "/agentbounty/devlog": "Devlog",
    "/agentbounty/explain": "Explain",
    "/agentbounty/faq": "FAQ",
    "/agentbounty/guides": "Guides",
    "/agentbounty/how-it-works": "How it works",
    "/agentbounty/legal": "Legal",
    "/agentbounty/legal/disclaimer": "Disclaimer",
    "/agentbounty/legal/privacy": "Privacy",
    "/agentbounty/legal/terms": "Terms",
    "/agentbounty/links": "Links",
    "/agentbounty/log": "Log",
    "/agentbounty/reference": "Reference",
    "/agentbounty/reference/evidence-schema": "Evidence schema",
    "/agentbounty/reviewers": "Reviewers",
    "/agentbounty/reviewers/economics": "Economics",
    "/agentbounty/roadmap": "Roadmap",
    "/agentbounty/staking": "Staking",
    "/agentbounty/start": "Start",
    "/agentbounty/status": "Status",
    "/agentbounty/token": "Token",
    "/plaintext/club": "Club",
    "/plaintext/manual": "Manual",
    "/plaintext/roadmap": "Roadmap",
    "/plaintext/spec": "Spec",
    "/rebase/docs": "Docs",
    "/rebase/docs/contracts": "Contracts",
    "/rebase/docs/fees": "Fees",
    "/rebase/docs/genesis": "Genesis",
    "/rebase/docs/rebase": "REBASE",
    "/rebase/source": "Source",
    "/reclaim/galleries": "Galleries",
    "/accumulator/docs": "Docs",
    "/accumulator/privacy": "Privacy",
    "/accumulator/terms": "Terms",
    "/coins/leaderboard": "Leaderboard",
}

SEGMENT_TITLES = {
    "file": "Filing",
    "docs": "Docs",
    "privacy": "Privacy",
    "terms": "Terms",
    "legal": "Legal",
    "source": "Source",
    "app": "App",
    "tr": "T\u00fcrk\u00e7e",
    "ledger": "Ledger",
    "reader": "Reader",
    "faq": "FAQ",
    "api": "API",
    "sdk": "SDK",
    "spec": "Spec",
    "mcp": "MCP",
    "rss": "RSS",
    "cv": "CV",
}

SMALL = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of",
    "on", "or", "the", "to", "vs", "via", "with", "over", "per",
}
ACRONYMS = {
    "ai", "agi", "api", "anki", "ccru", "csae", "cv", "dao", "defi", "faq",
    "fao", "html", "http", "ipfs", "ipo", "llm", "llms", "mcp", "nft", "nfts",
    "openapi", "pdf", "rss", "sdk", "sec", "sp100", "ubu", "usdc", "x402",
    "xmtp", "og", "url", "ui", "ux", "vc", "web3", "xml",
}

CORE_ROOTS = {
    "",
    "about",
    "cv",
    "links",
    "newsletter",
    "consulting",
    "products",
    "product-drafts",
    "writing",
    "privacy",
    "disclaimer",
    "agents",
    "raises",
    "offline",
    "moved",
}

CORE_ORDER = [
    "/",
    "/about/",
    "/cv/",
    "/links/",
    "/newsletter/",
    "/consulting/",
    "/products/",
    "/writing/",
    "/agents/",
    "/raises/",
    "/product-drafts/",
    "/privacy/",
    "/disclaimer/",
    "/offline/",
    "/moved/",
]

FEEDS = [
    (f"{SITE}/rss.xml", "Journal RSS"),
    (f"{SITE}/llms.txt", "llms.txt"),
    (f"{SITE}/llms-full.txt", "llms-full.txt"),
    (f"{SITE}/cv.md", "CV (Markdown)"),
    (f"{SITE}/cv/Gokhan_Turhan_CV.pdf", "CV (PDF)"),
    (f"{SITE}/search.json", "Search index"),
]

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}

DESCRIPTION = (
    "A complete, browsable sitemap of every page on gokhanturhan.com \u2014 "
    "products, journal, filings, publishing and the archive."
)


def curl(url: str, timeout: int = 45) -> bytes:
    result = subprocess.run(
        [
            "curl", "-fsSL",
            "-A", UA,
            "--max-time", str(timeout),
            "--retry", "3",
            "--retry-delay", "2",
            url,
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"curl failed for {url}: {err or result.returncode}")
    return result.stdout


def norm_path(path: str) -> str:
    if not path:
        return "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    if not path.startswith("/"):
        path = "/" + path
    return path or "/"


def public_url(path: str) -> str:
    p = path if path.startswith("/") else "/" + path
    if p != "/" and not p.endswith("/"):
        if re.search(r"\.[a-zA-Z0-9]{1,8}$", p):
            return SITE + p
        p = p + "/"
    return SITE + p


def first_segment(path: str) -> str:
    p = norm_path(path).strip("/")
    return p.split("/")[0] if p else ""


def titleize(slug: str) -> str:
    slug = slug.strip("/")
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug)
    parts = re.split(r"[-_]+", slug)
    out = []
    for i, part in enumerate(parts):
        low = part.lower()
        if not part:
            continue
        if low in ACRONYMS:
            token = low.upper()
            if low == "sp100":
                token = "S&P 100"
            out.append(token)
        elif part.isdigit() and len(part) == 4 and 1990 <= int(part) <= 2099:
            out.append(part)
        elif i != 0 and low in SMALL:
            out.append(low)
        elif low == "vs":
            out.append("vs")
        else:
            out.append(part[:1].upper() + part[1:])
    return " ".join(out) or slug


def resolve_title(path: str, extra: dict[str, str] | None = None) -> str:
    p = norm_path(path)
    if extra and p in extra:
        return extra[p]
    if p in TITLE_MAP:
        return TITLE_MAP[p]
    seg = first_segment(p)
    rest = p[len(seg) + 1 :].strip("/") if seg else p.strip("/")
    if seg in PRODUCT_NAMES and not rest:
        return PRODUCT_NAMES[seg]
    if rest == "file" or p.endswith("/file"):
        name = PRODUCT_NAMES.get(seg, titleize(seg))
        return f"{name} \u2014 Filing"
    m = re.fullmatch(r"/journal/(\d{4})", p)
    if m:
        return m.group(1)
    m = re.fullmatch(r"/journal/(\d{4})/(\d{2})", p)
    if m:
        return f"{MONTHS.get(m.group(2), m.group(2))} {m.group(1)}"
    m = re.fullmatch(r"/archive/categories/([^/]+)", p)
    if m:
        return titleize(m.group(1))
    m = re.fullmatch(r"/archive/tags/([^/]+)", p)
    if m:
        return titleize(m.group(1))
    leaf = p.rsplit("/", 1)[-1]
    if leaf in SEGMENT_TITLES:
        return SEGMENT_TITLES[leaf]
    return titleize(leaf)


def fetch_sitemap_urls() -> list[str]:
    raw = curl(SITEMAP_INDEX)
    root = ET.fromstring(raw)
    locs = [el.text.strip() for el in root.findall("sm:sitemap/sm:loc", SM_NS) if el.text]
    if not locs:
        if root.tag.endswith("urlset"):
            return [el.text.strip() for el in root.findall("sm:url/sm:loc", SM_NS) if el.text]
        locs = [f"{SITE}/sitemap-0.xml"]
    urls: list[str] = []
    for loc in locs:
        data = curl(loc)
        sroot = ET.fromstring(data)
        for el in sroot.findall("sm:url/sm:loc", SM_NS):
            if el.text:
                urls.append(el.text.strip())
    if not urls:
        raise RuntimeError("sitemap contained no URLs")
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def fetch_rss() -> dict[str, tuple[str, datetime | None]]:
    try:
        raw = curl(RSS_URL)
    except RuntimeError as e:
        print(f"warning: RSS fetch failed: {e}", file=sys.stderr)
        return {}
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"warning: RSS parse failed: {e}", file=sys.stderr)
        return {}
    out: dict[str, tuple[str, datetime | None]] = {}
    for item in root.findall(".//item"):
        link = (item.findtext("link") or "").strip()
        title = (item.findtext("title") or "").strip()
        pub = item.findtext("pubDate")
        dt = None
        if pub:
            try:
                dt = parsedate_to_datetime(pub)
            except (TypeError, ValueError):
                dt = None
        if not link:
            continue
        path = norm_path(urlparse(link).path)
        out[path] = (title or resolve_title(path), dt)
    return out


def fetch_search() -> dict[str, tuple[str, datetime | None]]:
    try:
        raw = curl(SEARCH_URL)
        data = json.loads(raw)
    except Exception as e:
        print(f"warning: search.json fetch failed: {e}", file=sys.stderr)
        return {}
    out: dict[str, tuple[str, datetime | None]] = {}
    if not isinstance(data, list):
        return out
    for item in data:
        link = (item.get("link") or "").strip()
        title = (item.get("title") or "").strip()
        if not link:
            continue
        path = norm_path(urlparse(link).path if link.startswith("http") else link)
        dt = None
        date = item.get("date")
        if date:
            try:
                dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
            except ValueError:
                dt = None
        if title:
            out[path] = (title, dt)
    return out


def is_journal_index(path: str) -> bool:
    return bool(re.fullmatch(r"/journal(/(\d{4}(/\d{2})?)?)?", norm_path(path)))


def is_journal_post(path: str) -> bool:
    p = norm_path(path)
    return p.startswith("/journal/") and not is_journal_index(p)


def classify(paths: list[str]) -> dict[str, list[str]]:
    product_roots = set(PRODUCT_NAMES)
    buckets: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        p = norm_path(path)
        seg = first_segment(p)
        if is_journal_post(p) or is_journal_index(p):
            buckets["journal"].append(p)
        elif seg in product_roots:
            buckets["products"].append(p)
        elif seg == "publishing" or p == "/publishing":
            buckets["publishing"].append(p)
        elif seg == "archive" or p == "/archive":
            buckets["archive"].append(p)
        elif seg in {"tools", "lists", "art", "haleanbar"}:
            buckets["tools"].append(p)
        elif seg in CORE_ROOTS or p == "/":
            buckets["core"].append(p)
        else:
            buckets["other"].append(p)
    return buckets


def core_sort_key(path: str) -> tuple:
    np = norm_path(path)
    if np == "/" or np == "/about":
        idx = CORE_ORDER.index("/" if np == "/" else "/about/")
        return (idx, 0, path)
    if np.startswith("/about/"):
        return (CORE_ORDER.index("/about/"), 1, resolve_title(path).lower())
    slashed = np if np == "/" else np + "/"
    if slashed in CORE_ORDER:
        return (CORE_ORDER.index(slashed), 0, path)
    return (len(CORE_ORDER), 0, path)


def product_groups(paths: list[str]):
    by: dict[str, list[str]] = defaultdict(list)
    for p in paths:
        by[first_segment(p)].append(p)
    featured_set = set(FEATURED)
    slugs = list(FEATURED) + sorted(
        (s for s in by if s not in featured_set),
        key=lambda s: PRODUCT_NAMES.get(s, s).lower(),
    )
    groups = []
    for slug in slugs:
        items = by.get(slug, [])
        if not items:
            continue
        root = f"/{slug}"
        filing = root + "/file" if (root + "/file") in items else None
        others = sorted(
            (p for p in items if p not in {root, filing}),
            key=lambda p: p,
        )
        groups.append(
            (slug, PRODUCT_NAMES.get(slug, titleize(slug)), filing, others, root if root in items else None)
        )
    return groups


def format_date(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # %-d is POSIX-only; also works on the Actions Ubuntu runner.
    return dt.strftime("%-d %b %Y")


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def entry_html(
    path: str,
    title: str,
    *,
    date: str = "",
    extra_class: str = "",
    depth: int = 0,
    filing_href: str | None = None,
    filing_title: str = "Filing",
    product: str = "",
    hay_extra: str = "",
) -> str:
    href = public_url(path)
    hay = " ".join(x for x in (title, path, href, hay_extra, date) if x).lower()
    cls = "entry" + (f" {extra_class}" if extra_class else "")
    style = f' style="--d:{depth}"' if depth else ""
    prod = f' data-product="{esc(product)}"' if product else ""
    filing = ""
    if filing_href:
        fh = public_url(filing_href)
        filing = f'<a class="filing" href="{esc(fh)}">{esc(filing_title)}</a>'
        hay = hay + " filing " + filing_title.lower() + " " + filing_href.lower()
    date_html = f'<time class="when">{esc(date)}</time>' if date else ""
    return (
        f'<li class="{cls}" data-hay="{esc(hay)}" data-path="{esc(path)}"{prod}{style}>'
        f"{date_html}"
        f'<a class="ttl" href="{esc(href)}">{esc(title)}</a>'
        f"{filing}"
        f"</li>"
    )


def child_map(paths: list[str]) -> dict[str, list[str]]:
    seen: set[str] = set()
    norms: list[str] = []
    for p in paths:
        n = norm_path(p)
        if n in seen:
            continue
        seen.add(n)
        norms.append(n)
    kids: dict[str, list[str]] = defaultdict(list)
    for n in norms:
        parent = n.rsplit("/", 1)[0]
        while parent and parent not in seen:
            parent = parent.rsplit("/", 1)[0] if "/" in parent else ""
        kids[parent].append(n)
    for key in kids:
        kids[key].sort()
    return kids


def render_nodes(parent: str, kids: dict[str, list[str]], extra: dict, product: str, name: str) -> str:
    parts = []
    for p in kids.get(parent, []):
        title = resolve_title(p, extra)
        sub = kids.get(p) or []
        if sub:
            inner = render_nodes(p, kids, extra, product, name)
            href = public_url(p)
            hay = " ".join(x for x in (title, p, href, name) if x).lower()
            prod = f' data-product="{esc(product)}"' if product else ""
            parts.append(
                f'<li class="entry nest sub" data-hay="{esc(hay)}" data-path="{esc(p)}"{prod}>'
                f'<details><summary><span class="twist" aria-hidden="true"></span>'
                f'<a class="ttl" href="{esc(href)}">{esc(title)}</a></summary>'
                f'<ul class="list">{inner}</ul></details></li>'
            )
        else:
            parts.append(
                entry_html(p, title, extra_class="sub", product=product, hay_extra=name)
            )
    return "\n".join(parts)


def group_nest(label: str, hay: str, path: str, inner: str, count: int, *, cloud: bool = False) -> str:
    ul = "cloud" if cloud else "list"
    return (
        f'<li class="entry nest group-nest" data-hay="{esc(hay)}" data-path="{esc(path)}">'
        f'<details><summary><span class="twist" aria-hidden="true"></span>'
        f'<span class="group-label">{esc(label)}</span>'
        f'<span class="count">{count}</span></summary>'
        f'<ul class="{ul}">{inner}</ul></details></li>'
    )


def section_html(sid: str, title: str, count: int, inner: str, *, open_: bool = True) -> str:
    opened = " open" if open_ else ""
    return (
        f'<section class="sec" id="{esc(sid)}" data-section="{esc(sid)}">'
        f"<details{opened}>"
        f"<summary>"
        f'<span class="sec-title">{esc(title)}</span>'
        f'<span class="count" data-count-total="{count}">{count}</span>'
        f"</summary>"
        f'<ul class="list">{inner}</ul>'
        f"</details>"
        f"</section>"
    )


def build_html(
    buckets: dict[str, list[str]],
    extra: dict[str, tuple[str, datetime | None]],
    titles_only: dict[str, str],
) -> tuple[str, dict[str, int], int]:
    counts: dict[str, int] = {}
    template_path = Path(__file__).resolve().parent / "sitemap_template.html"
    template = template_path.read_text(encoding="utf-8")

    # ---- core ----
    core_paths = sorted(buckets.get("core", []), key=core_sort_key)
    core_bits = []
    about_children = [p for p in core_paths if norm_path(p).startswith("/about/")]
    seen_about = False
    for p in core_paths:
        if norm_path(p).startswith("/about/"):
            continue
        if norm_path(p) == "/about":
            seen_about = True
            if about_children:
                inner = render_nodes("", child_map(about_children), titles_only, "", "about")
                href = public_url(p)
                title = resolve_title(p, titles_only)
                hay = " ".join(x for x in (title, p, href, " ".join(about_children)) if x).lower()
                core_bits.append(
                    f'<li class="entry nest" data-hay="{esc(hay)}" data-path="{esc(p)}">'
                    f'<details><summary><span class="twist" aria-hidden="true"></span>'
                    f'<a class="ttl" href="{esc(href)}">{esc(title)}</a></summary>'
                    f'<ul class="list">{inner}</ul></details></li>'
                )
            else:
                core_bits.append(entry_html(p, resolve_title(p, titles_only)))
            continue
        core_bits.append(entry_html(p, resolve_title(p, titles_only)))
    if about_children and not seen_about:
        for c in about_children:
            core_bits.append(entry_html(c, resolve_title(c, titles_only)))
    counts["core"] = len(core_paths)

    # ---- products ----
    groups = product_groups(buckets.get("products", []))
    prod_bits = []
    prod_count = 0
    for slug, name, filing, others, root in groups:
        child_html = render_nodes("", child_map(others), titles_only, slug, name) if others else ""
        if root and child_html:
            href = public_url(root)
            hay = " ".join(x for x in (name, root, href, " ".join(others)) if x).lower()
            filing_html = ""
            if filing:
                fh = public_url(filing)
                filing_html = f'<a class="filing" href="{esc(fh)}">Filing</a>'
                hay += " filing " + filing.lower()
            prod_bits.append(
                f'<li class="entry product-root nest" data-hay="{esc(hay)}" data-path="{esc(root)}" data-product="{esc(slug)}">'
                f'<details><summary><span class="twist" aria-hidden="true"></span>'
                f'<a class="ttl" href="{esc(href)}">{esc(name)}</a>{filing_html}</summary>'
                f'<ul class="list">{child_html}</ul></details></li>'
            )
            prod_count += 1
            if filing:
                prod_count += 1
            prod_count += len(others)
        elif root:
            prod_bits.append(
                entry_html(
                    root,
                    name,
                    extra_class="product-root",
                    filing_href=filing,
                    product=slug,
                    hay_extra=" ".join(others),
                )
            )
            prod_count += 1
            if filing:
                prod_count += 1
        elif filing:
            prod_bits.append(entry_html(filing, f"{name} \u2014 Filing", product=slug))
            prod_count += 1
            if child_html:
                prod_bits.append(child_html)
                prod_count += len(others)
        elif child_html:
            prod_bits.append(child_html)
            prod_count += len(others)
    counts["products"] = prod_count

    # ---- journal ----
    posts = []
    indexes = []
    for p in buckets.get("journal", []):
        if is_journal_post(p):
            title = resolve_title(p, titles_only)
            dt = None
            if p in extra:
                title = extra[p][0] or title
                dt = extra[p][1]
            posts.append((dt or datetime(1970, 1, 1, tzinfo=timezone.utc), p, title, dt))
        else:
            indexes.append(p)
    posts.sort(key=lambda t: t[0], reverse=True)
    jour_bits = []
    if "/journal" in [norm_path(x) for x in indexes]:
        jour_bits.append(entry_html("/journal", "All posts", extra_class="index-row"))
    for _, p, title, dt in posts:
        jour_bits.append(entry_html(p, title, date=format_date(dt), extra_class="post"))
    month_indexes = [p for p in indexes if norm_path(p) != "/journal"]
    month_indexes.sort(reverse=True)
    if month_indexes:
        inner_m = "\n".join(
            entry_html(p, resolve_title(p, titles_only), extra_class="sub idx")
            for p in month_indexes
        )
        jour_bits.append(
            '<li class="entry months-wrap" data-hay="year month archive journal indexes" data-path="/journal/">'
            '<details class="inner">'
            f'<summary><span class="twist" aria-hidden="true"></span><span class="sec-title">By year and month</span>'
            f'<span class="count">{len(month_indexes)}</span></summary>'
            f'<ul class="list">{inner_m}</ul>'
            "</details></li>"
        )
    counts["journal"] = len(buckets.get("journal", []))

    # ---- publishing ----
    pub_paths = sorted(buckets.get("publishing", []))
    pub_bits = [render_nodes("", child_map(pub_paths), titles_only, "", "publishing")]
    counts["publishing"] = len(pub_paths)

    # ---- tools / lists / art ----
    tools_order = ["/tools", "/lists", "/art", "/haleanbar"]
    tools_paths = sorted(
        buckets.get("tools", []),
        key=lambda p: (
            tools_order.index(norm_path(p)) if norm_path(p) in tools_order else 99,
            p,
        ),
    )
    tools_bits = [entry_html(p, resolve_title(p, titles_only)) for p in tools_paths]
    counts["tools"] = len(tools_paths)

    # ---- archive ----
    arch = buckets.get("archive", [])
    arch_root = [p for p in arch if norm_path(p) == "/archive"]
    cats = sorted(
        [p for p in arch if norm_path(p).startswith("/archive/categories")],
        key=lambda p: resolve_title(p, titles_only).lower(),
    )
    tags_index = [p for p in arch if norm_path(p) == "/archive/tags"]
    tags = sorted(
        [p for p in arch if norm_path(p).startswith("/archive/tags/")],
        key=lambda p: resolve_title(p, titles_only).lower(),
    )
    arch_bits = []
    for p in arch_root:
        arch_bits.append(entry_html(p, "Archive"))
    if cats:
        cat_inner = "\n".join(
            entry_html(p, resolve_title(p, titles_only), extra_class="tag") for p in cats
        )
        arch_bits.append(
            group_nest(
                "Categories",
                "archive categories " + " ".join(cats),
                "/archive/categories/",
                cat_inner,
                len(cats),
                cloud=True,
            )
        )
    if tags_index:
        arch_bits.append(entry_html("/archive/tags", "All tags", extra_class="index-row"))
    if tags:
        tag_inner = "\n".join(
            entry_html(p, resolve_title(p, titles_only), extra_class="tag") for p in tags
        )
        arch_bits.append(
            group_nest(
                "Tags",
                "archive tags " + " ".join(tags),
                "/archive/tags/",
                tag_inner,
                len(tags),
                cloud=True,
            )
        )
    counts["archive"] = len(arch)

    # ---- other ----
    other_paths = sorted(buckets.get("other", []))
    other_bits = [entry_html(p, resolve_title(p, titles_only)) for p in other_paths]
    counts["other"] = len(other_paths)

    # ---- feeds ----
    feed_bits = []
    for href, title in FEEDS:
        hay = f"{title} {href}".lower()
        feed_bits.append(
            f'<li class="entry" data-hay="{esc(hay)}" data-path="{esc(urlparse(href).path)}">'
            f'<a class="ttl" href="{esc(href)}">{esc(title)}</a>'
            f'<span class="hint">{esc(urlparse(href).path)}</span>'
            "</li>"
        )
    counts["feeds"] = len(FEEDS)

    sections = [
        section_html("core", "Home & core pages", counts["core"], "\n".join(core_bits)),
        section_html("products", "Products", counts["products"], "\n".join(prod_bits)),
        section_html("journal", "Journal", counts["journal"], "\n".join(jour_bits)),
        section_html("publishing", "Publishing", counts["publishing"], "\n".join(pub_bits)),
        section_html("tools", "Tools, lists & art", counts["tools"], "\n".join(tools_bits)),
        section_html("archive", "Archive", counts["archive"], "\n".join(arch_bits)),
    ]
    if other_paths:
        sections.append(section_html("other", "Other", counts["other"], "\n".join(other_bits)))
    sections.append(section_html("feeds", "Feeds", counts["feeds"], "\n".join(feed_bits)))

    total = sum(counts.values())

    toc_items = [
        ("core", "Home & core"),
        ("products", "Products"),
        ("journal", "Journal"),
        ("publishing", "Publishing"),
        ("tools", "Tools, lists & art"),
        ("archive", "Archive"),
    ]
    if other_paths:
        toc_items.append(("other", "Other"))
    toc_items.append(("feeds", "Feeds"))
    toc = "\n".join(
        f'<a href="#{esc(sid)}">{esc(label)} <span class="toc-n" data-for="{esc(sid)}">{counts[sid]}</span></a>'
        for sid, label in toc_items
    )

    page = (
        template
        .replace("{{DESCRIPTION}}", esc(DESCRIPTION))
        .replace("{{TOC}}", toc)
        .replace("{{SECTIONS}}", "\n".join(sections))
        .replace("{{TOTAL}}", str(total))
    )
    # Deterministic trailing newline
    if not page.endswith("\n"):
        page += "\n"
    return page, counts, total


def extra_titles(rss: dict, search: dict):
    merged: dict[str, tuple[str, datetime | None]] = {}
    titles: dict[str, str] = {}
    for src in (search, rss):
        for path, (title, dt) in src.items():
            prev = merged.get(path)
            if prev:
                title = title or prev[0]
                dt = dt or prev[1]
            merged[path] = (title, dt)
            if title:
                titles[path] = title
    return merged, titles


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    print("Fetching sitemap\u2026", flush=True)
    raw_urls = fetch_sitemap_urls()
    paths = []
    for u in raw_urls:
        if is_site_host(urlparse(u).netloc):
            paths.append(norm_path(urlparse(u).path))
    if not paths:
        paths = [norm_path(urlparse(u).path) for u in raw_urls]
    print(f"  {len(paths)} URLs", flush=True)

    print("Fetching RSS and search index\u2026", flush=True)
    rss = fetch_rss()
    search = fetch_search()
    extra, titles = extra_titles(rss, search)
    print(f"  RSS {len(rss)} items, search {len(search)} items, titles {len(titles)}", flush=True)

    buckets = classify(paths)
    page, counts, total = build_html(buckets, extra, titles)

    dest = repo / "index.html"
    old = dest.read_text(encoding="utf-8") if dest.exists() else None
    if old == page:
        print("index.html unchanged.")
    else:
        dest.write_text(page, encoding="utf-8")
        print(f"Wrote {dest} ({len(page)} bytes, {total} links).")

    print("Counts:")
    for k, v in counts.items():
        print(f"  {k:12s} {v}")
    print(f"  {'TOTAL':12s} {total}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
