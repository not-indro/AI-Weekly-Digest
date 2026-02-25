# AI Weekly Digest — Automated Briefing with AI

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fnot-indro%2FAI-Weekly-Digest&env=TAVILY_API_KEY,GROQ_API_KEY&project-name=ai-weekly-digest&repository-name=AI-Weekly-Digest)
![License](https://img.shields.io/github/license/not-indro/AI-Weekly-Digest?color=blue)
![Python](https://img.shields.io/badge/python-3.9+-yellow)

An open-source, automated pipeline that generates a high-quality weekly AI briefing. It searches multiple sources, verifies links, scrapes content, and uses Llama 3 summarization to produce a polished, Outlook-ready newsletter.

---

## ✨ Key Features

- **7 Curated Sections**: Trending AI, Indian News, Global Policy, Events, AI Progress, Plain-Language Research, and Deep Dive Reports.
- **Multi-Source Intelligence**: Tavily Search, Hacker News, Product Hunt, arXiv, PapersWithCode, and 12+ curated RSS feeds.
- **Smart Filtering**: Automatic paywall detection, link verification (404/SSL), and URL deduplication.
- **LLM Summarization**: Powered by **Groq (Llama 3.1 70B)** for lightning-fast, section-aware insights.
- **Premium Dashboard**: Modern web interface with real-time generation tracking and one-click HTML download.

---

## 🚀 Quick Start (Vercel)

The fastest way to get your own instance running:

1. **Fork** this repository.
2. **Deploy to Vercel**: Click the "Deploy" button above or import your fork manually.
3. **Configure Environment Variables** in Vercel:
   - `TAVILY_API_KEY`: Get one at [tavily.com](https://tavily.com) (Free tier available).
   - `GROQ_API_KEY`: Get one at [console.groq.com](https://console.groq.com) (Free tier available).
4. **Redeploy**: Once keys are added, your dashboard is ready!

---

## 💻 Local Development

```bash
# Clone the repository
git clone https://github.com/not-indro/AI-Weekly-Digest.git
cd AI-Weekly-Digest

# Setup virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env and add your API keys

# Start local server
python local_dev_server.py
```
Open [http://localhost:8000](http://localhost:8000) to see the dashboard.

---

## 🏗️ Architecture & Logic

### Project Structure
```text
├── api/                     # Vercel Serverless (Python)
│   ├── generate_section.py  # Orchestrates search + summary
│   ├── search_section.py    # Per-section discovery endpoint
│   ├── summarize_section.py # LLM summarization wrapper
│   ├── render.py            # Final Jinja2 HTML assembly
│   └── health.py            # API health monitoring
├── public/                  # Frontend Dashboard
│   ├── index.html           # Glassmorphic UI
│   ├── style.css            # Modern dark-mode styling
│   └── app.js               # Async state & progress management
├── ai_newsletter_automation/ # Core Engine
│   ├── runner.py            # Entry point for generation pipeline
│   ├── search.py            # Multi-source scrapers (HN, RSS, Tavily)
│   ├── verify.py            # Paywall & link validity checker
│   ├── scrape.py            # HTML-to-Text cleaner
│   ├── summarize.py         # Groq LLM integration
│   ├── rerank.py            # Relevance-based scoring
│   └── models.py            # Pydantic data structures
└── template/                # Newsletter Themes
    └── newsletter.html.j2   # Responsive Jinja2 MJML-like template
```

### ⚙️ How it Works
1.  **Discovery**: The engine triggers simultaneous searches across Tavily (Web), Hacker News (Trending), arXiv (Research), and 12+ curated AI lab RSS feeds.
2.  **Verification**: Links are checked for 404s, SSL issues, and common paywall fingerprinting.
3.  **Extraction**: Valid articles are stripped of JS/Ads and converted into clean Markdown-like text for the LLM.
4.  **Intelligence**: **GROQ (Llama 3.1 70B)** summarizes the content, scores it for relevance, and extracts key insights into structured JSON.
5.  **Assembly**: The dashboard collects these JSON chunks and renders a final, Outlook-compatible HTML newsletter using Jinja2 templates.


---

## 📧 Newsletter Sections

| Section | Focus | Sources |
| :--- | :--- | :--- |
| **Trending AI** | Major launches & news | HN, Product Hunt, RSS |
| **Indian News** | Indian AI ecosystem | Local outlets, Tavily |
| **Global News** | Regulation & Ethics | OECD, G7, Major Govs |
| **Events** | Conferences & Webinars | Curated calendars |
| **AI Progress** | SOTA & Benchmarks | PapersWithCode |
| **Research** | Plain-language papers | arXiv |
| **Deep Dive** | Long-form reports | NIST, MIT, Stanford |

---

## 🛠️ Configuration

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `TAVILY_API_KEY` | **Yes** | Web search and source discovery |
| `GROQ_API_KEY` | **Yes** | LLM summarization and analysis |
| `MAX_PER_STREAM` | No | Limit articles per section (Default: auto) |

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

<p align="center">
  Built with ❤️ for the AI Community by <a href="https://github.com/not-indro">not-indro</a>
</p>
# AI-Weekly-Digest
