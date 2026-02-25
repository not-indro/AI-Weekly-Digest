from datetime import date
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs, urljoin

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import SummaryItem
from .search import DEFAULT_STREAMS


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Build display-name lookup from the canonical SectionConfig definitions
SECTION_LABELS: Dict[str, str] = {key: cfg.name for key, cfg in DEFAULT_STREAMS.items()}

SECTION_LABELS_FR: Dict[str, str] = {
    "trending": "IA en vedette",
    "indian": "Nouvelles indiennes",
    "global": "Nouvelles internationales",
    "events": "Événements",
    "ai_progress": "Progrès en IA",
    "research_plain": "Recherche en IA",
    "deep_dive": "Analyse approfondie",
}

SECTION_LABELS_HI: Dict[str, str] = {
    "trending": "ट्रेंडिंग AI",
    "indian": "भारतीय समाचार",
    "global": "वैश्विक समाचार",
    "events": "कार्यक्रम",
    "ai_progress": "AI प्रगति",
    "research_plain": "AI अनुसंधान",
    "deep_dive": "गहन विश्लेषण",
}

SECTION_LABELS_ES: Dict[str, str] = {
    "trending": "IA en Tendencia",
    "indian": "Noticias Indias",
    "global": "Noticias Globales",
    "events": "Eventos",
    "ai_progress": "Progreso en IA",
    "research_plain": "Investigación en IA",
    "deep_dive": "Análisis Profundo",
}

SECTION_LABELS_DE: Dict[str, str] = {
    "trending": "KI im Trend",
    "indian": "Indische Nachrichten",
    "global": "Globale Nachrichten",
    "events": "Veranstaltungen",
    "ai_progress": "KI Fortschritt",
    "research_plain": "KI Forschung",
    "deep_dive": "Tiefgreifende Analyse",
}

SECTION_LABELS_ZH: Dict[str, str] = {
    "trending": "热门AI",
    "indian": "印度新闻",
    "global": "全球新闻",
    "events": "活动",
    "ai_progress": "AI进展",
    "research_plain": "AI研究",
    "deep_dive": "深度分析",
}

SECTION_LABELS_JA: Dict[str, str] = {
    "trending": "トレンドAI",
    "indian": "インドのニュース",
    "global": "グローバルニュース",
    "events": "イベント",
    "ai_progress": "AIの進歩",
    "research_plain": "AI研究",
    "deep_dive": "詳細分析",
}

SECTION_DESCRIPTIONS: Dict[str, str] = {
    "trending": "The biggest AI stories everyone is talking about this week.",
    "indian": "AI developments affecting Indian federal and state policy.",
    "global": "International AI governance, regulation, and workforce policy.",
    "events": "Upcoming AI conferences, summits, and workshops.",
    "ai_progress": "Notable benchmark results and technical capability milestones.",
    "research_plain": "Cutting-edge AI research and breakthroughs.",
    "deep_dive": "In-depth reports and analyses from leading AI organizations.",
}

SECTION_DESCRIPTIONS_FR: Dict[str, str] = {
    "trending": "Les plus grandes nouvelles en IA dont tout le monde parle cette semaine.",
    "indian": "Développements en IA touchant directement les politiques fédérales et étatiques indiennes.",
    "global": "Gouvernance, réglementation et politiques internationales en matière d'IA.",
    "events": "Conférences, sommets et ateliers en IA à venir.",
    "ai_progress": "Résultats de référence et jalons techniques notables.",
    "research_plain": "Recherche de pointe et percées en IA.",
    "deep_dive": "Rapports et analyses approfondis des grandes organisations en IA.",
}

SECTION_DESCRIPTIONS_HI: Dict[str, str] = {
    "trending": "इस सप्ताह की सबसे बड़ी AI खबरें जिनकी हर कोई बात कर रहा है।",
    "indian": "भारतीय संघीय और राज्य नीति को प्रभावित करने वाले AI विकास।",
    "global": "अंतर्राष्ट्रीय AI शासन, नियमन और कार्यबल नीति।",
    "events": "आगामी AI सम्मेलन, शिखर सम्मेलन और कार्यशालाएं।",
    "ai_progress": "उल्लेखनीय बेंचमार्क परिणाम और तकनीकी क्षमता मील के पत्थर।",
    "research_plain": "अत्याधुनिक AI अनुसंधान और सफलताएं।",
    "deep_dive": "प्रमुख AI संगठनों से गहन रिपोर्ट और विश्लेषण।",
}

SECTION_DESCRIPTIONS_ES: Dict[str, str] = {
    "trending": "Las noticias de IA más importantes de las que todos hablan esta semana.",
    "indian": "Desarrollos de IA que afectan las políticas federales y estatales de India.",
    "global": "Gobernanza internacional de IA, regulación y políticas laborales.",
    "events": "Próximas conferencias, cumbres y talleres sobre IA.",
    "ai_progress": "Resultados de evaluación notables e hitos de capacidad técnica.",
    "research_plain": "Investigación y avances pioneros en IA.",
    "deep_dive": "Informes y análisis en profundidad de organizaciones líderes en IA.",
}

SECTION_DESCRIPTIONS_DE: Dict[str, str] = {
    "trending": "Die größten KI-Nachrichten, über die diese Woche alle sprechen.",
    "indian": "KI-Entwicklungen, die die indische Bundes- und Landespolitik beeinflussen.",
    "global": "Internationale KI-Governance, Regulierung und Arbeitsmarktpolitik.",
    "events": "Anstehende KI-Konferenzen, Gipfeltreffen und Workshops.",
    "ai_progress": "Bemerkenswerte Benchmark-Ergebnisse und Meilensteine technischer Fähigkeiten.",
    "research_plain": "Bahnbrechende KI-Forschung und Durchbrüche.",
    "deep_dive": "Ausführliche Berichte und Analysen von führenden KI-Organisationen.",
}

SECTION_DESCRIPTIONS_ZH: Dict[str, str] = {
    "trending": "本周大家都在谈论的最重大的AI新闻。",
    "indian": "影响印度联邦和邦政策的AI发展。",
    "global": "国际AI治理、监管和劳动力政策。",
    "events": "即将举行的AI会议、峰会和研讨会。",
    "ai_progress": "显著的基准测试结果和技术能力里程碑。",
    "research_plain": "前沿的AI研究和突破。",
    "deep_dive": "来自领先AI组织的深度报告和分析。",
}

SECTION_DESCRIPTIONS_JA: Dict[str, str] = {
    "trending": "今週誰もが話している最大のAIニュース。",
    "indian": "インドの連邦および州の政策に影響を与えるAI開発。",
    "global": "国際的なAIガバナンス、規制、および労働政策。",
    "events": "開催予定のAI会議、サミット、およびワークショップ。",
    "ai_progress": "注目すべきベンチマーク結果と技術的能力のマイルストーン。",
    "research_plain": "最先端のAI研究と画期的な進歩。",
    "deep_dive": "主要なAI組織による詳細なレポートと分析。",
}

# UI strings for template chrome
UI_STRINGS = {
    "en": {
        "title": "AI This Week",
        "date_label": "Date:",
        "tldr_title": "⚡ TL;DR — This Week's Top 3",
        "top_story": "🔥 Top Story",
        "read_more": "Read more →",
        "footer_line1": "AI This Week",
        "footer_line2": "Automated Briefing System",
    },
    "fr": {
        "title": "IA cette semaine",
        "date_label": "Date :",
        "tldr_title": "⚡ En bref — Les 3 faits saillants",
        "top_story": "🔥 À la une",
        "read_more": "Lire la suite →",
        "footer_line1": "🇮🇳 IA cette semaine — Bulletin automatisé sur l'IA.",
        "footer_line2": "Sélectionné avec soin. Propulsé par l'intelligence ouverte.",
    },
    "hi": {
        "title": "इस सप्ताह AI",
        "date_label": "दिनांक:",
        "tldr_title": "⚡ संक्षिप्त विवरण — इस सप्ताह की शीर्ष 3 खबरें",
        "top_story": "🔥 प्रमुख खबर",
        "read_more": "और पढ़ें →",
        "footer_line1": "इस सप्ताह AI — स्वचालित ब्रीफिंग प्रणाली।",
        "footer_line2": "सावधानीपूर्वक चयनित। ओपन इंटेलिजेंस द्वारा संचालित।",
    },
    "es": {
        "title": "IA Esta Semana",
        "date_label": "Fecha:",
        "tldr_title": "⚡ En Resumen — Las 3 mejores de esta semana",
        "top_story": "🔥 Noticia Principal",
        "read_more": "Leer más →",
        "footer_line1": "IA Esta Semana — Sistema de Sesiones Informativas Automatizadas.",
        "footer_line2": "Seleccionado cuidadosamente. Impulsado por inteligencia abierta.",
    },
    "de": {
        "title": "KI diese Woche",
        "date_label": "Datum:",
        "tldr_title": "⚡ Zusammenfassung — Top 3 der Woche",
        "top_story": "🔥 Top-Story",
        "read_more": "Weiterlesen →",
        "footer_line1": "KI diese Woche — Automatisiertes Briefing-System.",
        "footer_line2": "Sorgfältig ausgewählt. Angetrieben von Open Intelligence.",
    },
    "zh": {
        "title": "本周AI",
        "date_label": "日期:",
        "tldr_title": "⚡ 摘要 — 本周三大新闻",
        "top_story": "🔥 头条新闻",
        "read_more": "阅读更多 →",
        "footer_line1": "本周AI — 自动简报系统。",
        "footer_line2": "精心挑选。由人工智能提供支持。",
    },
    "ja": {
        "title": "今週のAI",
        "date_label": "日付:",
        "tldr_title": "⚡ 要約 — 今週のトップ3",
        "top_story": "🔥 トップニュース",
        "read_more": "続きを読む →",
        "footer_line1": "今週のAI — 自動ブリーフィングシステム。",
        "footer_line2": "厳選。オープンインテリジェンスを搭載。",
    },
}


def _add_utm(url: str, section_key: str, run_date: str) -> str:
    """Append UTM tracking parameters to a URL for engagement analytics."""
    if not url:
        return url
    try:
        parsed = urlparse(url)
        existing_params = parse_qs(parsed.query)
        utm_params = {
            "utm_source": "ai_this_week",
            "utm_medium": "email",
            "utm_campaign": run_date,
            "utm_content": section_key,
        }
        # Don't overwrite existing UTM params
        for k, v in utm_params.items():
            if k not in existing_params:
                existing_params[k] = [v]
        new_query = urlencode(existing_params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return url  # on any parsing error, return original


def _get_env() -> Environment:
    loader = FileSystemLoader(str(PROJECT_ROOT / "template"))
    env = Environment(loader=loader, autoescape=select_autoescape(["html", "xml"]))
    return env


def render_newsletter(
    sections: Dict[str, List[SummaryItem]],
    run_date: str | None = None,
    tldr: Optional[List[str]] = None,
    lang: str = "en",
) -> str:
    env = _get_env()
    template = env.get_template("newsletter.html.j2")

    effective_date = run_date or date.today().isoformat()

    # Sort events by date when available
    if "events" in sections:
        events = sections["events"]
        sections["events"] = sorted(
            events,
            key=lambda x: x.Date or "",
        )

    # Apply UTM tracking to all Live_Link URLs
    for section_key, items in sections.items():
        for item in items:
            if item.Live_Link:
                item.Live_Link = _add_utm(item.Live_Link, section_key, effective_date)

    # Select language-specific resources
    if lang == "fr":
        labels = SECTION_LABELS_FR
        descriptions = SECTION_DESCRIPTIONS_FR
    elif lang == "hi":
        labels = SECTION_LABELS_HI
        descriptions = SECTION_DESCRIPTIONS_HI
    elif lang == "es":
        labels = SECTION_LABELS_ES
        descriptions = SECTION_DESCRIPTIONS_ES
    elif lang == "de":
        labels = SECTION_LABELS_DE
        descriptions = SECTION_DESCRIPTIONS_DE
    elif lang == "zh":
        labels = SECTION_LABELS_ZH
        descriptions = SECTION_DESCRIPTIONS_ZH
    elif lang == "ja":
        labels = SECTION_LABELS_JA
        descriptions = SECTION_DESCRIPTIONS_JA
    else:
        labels = SECTION_LABELS
        descriptions = SECTION_DESCRIPTIONS
        
    strings = UI_STRINGS.get(lang, UI_STRINGS["en"])
    strings = UI_STRINGS.get(lang, UI_STRINGS["en"])

    return template.render(
        run_date=effective_date,
        sections=sections,
        section_labels=labels,
        section_descriptions=descriptions,
        tldr=tldr or [],
        lang=lang,
        ui=strings,
    )


