# AI Weekly Digest — Automated Briefing with AI

An open-source, automated pipeline that generates a weekly AI briefing. Searches multiple sources, verifies links, scrapes content, and uses LLM summarization to produce a polished, Outlook-ready newsletter.

## Features

- **9 curated sections**: Trending AI, Indian News, Global News, Events, CSPS/Public-Servant Events, Grain/Agri-Tech, AI Progress, Plain-Language Research, Deep Dive
- **Multi-source collection**: Tavily search, Hacker News, Product Hunt, arXiv, PapersWithCode, 9 curated RSS feeds (OpenAI, Anthropic, DeepMind, Meta AI, Google AI, Microsoft Research, OECD.AI, GovTech, Stanford HAI)
- **Smart filtering**: Paywall detection (text phrases + JSON-LD), link verification, URL deduplication
- **LLM summarization**: Groq (Llama 3.1 70B) with section-aware prompts and JSON-only output
- **Web interface**: Premium dashboard with live progress tracking, section-by-section generation, and HTML download
- **CLI mode**: Local command-line usage for power users

## Quick Start (Vercel)

> **⚠️ Required:** The app will not work without API keys set in Vercel. Both keys below are free-tier eligible.

1. **Fork** this repo on GitHub
2. **Import** it in [Vercel](https://vercel.com)
3. **Set environment variables** in Vercel → Project Settings → Environment Variables:
   - `TAVILY_API_KEY` — get one at [tavily.com](https://tavily.com)
   - `GROQ_API_KEY` — get one at [console.groq.com](https://console.groq.com)
4. **Redeploy** after adding the keys — Vercel will handle the rest

## Local Development

```bash
# Clone and setup
git clone https://github.com/your-username/ai-weekly-digest.git
cd ai-weekly-digest
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run CLI
python -m ai_newsletter_automation.runner --since-days 7 --dry-run
# Output → output/newsletter.html
```

### CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--since-days N` | Search window in days | 7 |
| `--date YYYY-MM-DD` | Override newsletter date | today |
| `--max-per-stream N` | Max articles per section | auto |
| `--dry-run` | Write HTML only (no Outlook) | off |

## Architecture

```
ai_newsletter_automation/
├── api/                        # Vercel serverless functions
│   ├── generate_section.py     # Per-section generation endpoint
│   ├── render.py               # Jinja2 HTML rendering endpoint
│   └── health.py               # Health check
├── public/                     # Static frontend
│   ├── index.html
│   ├── style.css
│   └── app.js
├── ai_newsletter_automation/   # Core Python pipeline
│   ├── config.py               # Settings from env vars
│   ├── models.py               # Data models (ArticleHit, SummaryItem, etc.)
│   ├── search.py               # Multi-source article search
│   ├── verify.py               # Link verification + paywall detection
│   ├── scrape.py               # HTML → text extraction
│   ├── summarize.py            # Groq LLM summarization
│   ├── assemble.py             # Jinja2 newsletter rendering
│   └── runner.py               # CLI + process_section() API
├── template/
│   └── newsletter.html.j2      # Newsletter HTML template
├── vercel.json                 # Vercel deployment config
└── requirements.txt
```

## Newsletter Sections

| Section | Source | Items |
|---------|--------|-------|
| Trending AI | HN + Product Hunt + RSS + Tavily | 8 |
| Indian News | Tavily (India-focused queries) | 5 |
| Global News | Tavily (policy/workforce focus) | 5 |
| Events | Tavily (conferences/webinars) | 4 |
| Public-Servant Events | Tavily (CSPS domain-locked) | 4 |
| Grain / Agri-Tech | Tavily (agriculture + ML) | 3 |
| AI Progress | PapersWithCode trending | 3 |
| Plain-Language Research | arXiv API (cs.AI, cs.LG, stat.ML) | 3 |
| Deep Dive | Tavily (OECD, Anthropic, MIT reports) | 2 |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TAVILY_API_KEY` | Yes | Web search API key |
| `GROQ_API_KEY` | Yes | LLM summarization API key |
| `RUN_DAYS` | No | Default search window (default: 7) |
| `MAX_PER_STREAM` | No | Override max items per section |

## License

MIT
