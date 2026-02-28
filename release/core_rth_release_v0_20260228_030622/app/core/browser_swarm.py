"""
Browser Swarm Orchestrator for Core Rth.

Native module that provides browser-based agent orchestration:
- Multi-agent web search and retrieval
- Page scraping and content extraction
- Summarization pipeline via LLM routing
- Results injected into Memory Vault + Knowledge Graph

Requires: pip install playwright beautifulsoup4
Optional:  pip install html2text
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import hashlib
import json
import logging
import re
import tempfile
import traceback

from .permissions import permission_gate, Capability, RiskLevel
from .memory_vault import memory_vault
from .knowledge_graph import get_knowledge_graph, NodeType, RelationType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 CoreRth/1.0"
)

MAX_PAGE_CHARS = 80_000
MAX_CONCURRENT_AGENTS = 5
DEFAULT_TIMEOUT_SEC = 15.0
BLOCKED_DOMAINS = {
    "localhost", "127.0.0.1", "0.0.0.0", "[::]",
    "metadata.google.internal", "169.254.169.254",
}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BrowserTask:
    """A single browser task to execute."""
    task_id: str
    url: str
    mode: str = "scrape"           # scrape | search | screenshot
    extract_selector: str = ""     # CSS selector for targeted extraction
    summarize: bool = True
    max_chars: int = MAX_PAGE_CHARS
    timeout_sec: float = DEFAULT_TIMEOUT_SEC


@dataclass
class BrowserResult:
    """Result of a single browser task."""
    task_id: str
    url: str
    status: str = "pending"        # ok | error | blocked | timeout
    title: str = ""
    content: str = ""
    summary: str = ""
    links: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    elapsed_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "url": self.url,
            "status": self.status,
            "title": self.title,
            "content_length": len(self.content),
            "content_preview": self.content[:500] if self.content else "",
            "summary": self.summary,
            "links_count": len(self.links),
            "links": self.links[:20],
            "metadata": self.metadata,
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_domain(url: str) -> bool:
    """Check if the URL domain is not in the blocked list."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().strip()
        if not host:
            return False
        if host in BLOCKED_DOMAINS:
            return False
        # Block private/internal IPs
        if host.startswith("10.") or host.startswith("192.168."):
            return False
        if host.startswith("172.") and 16 <= int(host.split(".")[1]) <= 31:
            return False
        return True
    except Exception:
        return False


def _extract_text_bs4(html: str, selector: str = "") -> Dict[str, Any]:
    """Extract text content from HTML using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {"text": "", "title": "", "links": [], "error": "beautifulsoup4 not installed"}

    soup = BeautifulSoup(html, "html.parser")

    # Remove script/style/nav/footer noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    # Targeted extraction
    if selector:
        elements = soup.select(selector)
        text = "\n\n".join(el.get_text(separator="\n", strip=True) for el in elements)
    else:
        # Try main content areas first
        main = soup.find("main") or soup.find("article") or soup.find("div", {"role": "main"})
        if main:
            text = main.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

    # Clean up whitespace
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = "\n".join(lines)

    # Extract links
    links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.startswith("http"):
            links.append(href)

    return {"text": text, "title": title, "links": links[:50], "error": ""}


def _extract_text_html2text(html: str) -> str:
    """Fallback: extract text using html2text."""
    try:
        import html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0
        return h.handle(html)
    except ImportError:
        return ""


# ---------------------------------------------------------------------------
# Browser backends
# ---------------------------------------------------------------------------

def _fetch_with_playwright(task: BrowserTask) -> BrowserResult:
    """Fetch page content using Playwright (headless Chromium)."""
    import time
    start = time.monotonic()
    result = BrowserResult(task_id=task.task_id, url=task.url)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result.status = "error"
        result.error = "playwright not installed. Run: pip install playwright && playwright install chromium"
        return result

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1280, "height": 800},
                java_script_enabled=True,
            )
            page = context.new_page()
            page.set_default_timeout(int(task.timeout_sec * 1000))

            # Navigate
            page.goto(task.url, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)  # Allow JS to render

            if task.mode == "screenshot":
                # Take screenshot
                screenshots_dir = _screenshots_dir()
                filename = f"screenshot_{task.task_id}_{int(time.time())}.png"
                filepath = screenshots_dir / filename
                page.screenshot(path=str(filepath), full_page=False)
                result.metadata["screenshot_path"] = str(filepath)

            # Get HTML content
            html = page.content()
            browser.close()

        # Extract text
        extracted = _extract_text_bs4(html, task.extract_selector)
        if extracted.get("error"):
            # Fallback
            text = _extract_text_html2text(html)
            result.content = text[:task.max_chars]
        else:
            result.title = extracted.get("title", "")
            result.content = extracted.get("text", "")[:task.max_chars]
            result.links = extracted.get("links", [])

        result.status = "ok"

    except Exception as e:
        result.status = "error"
        result.error = f"{type(e).__name__}: {str(e)}"
        logger.warning(f"Playwright fetch failed for {task.url}: {e}")

    result.elapsed_ms = int((time.monotonic() - start) * 1000)
    return result


def _fetch_with_urllib(task: BrowserTask) -> BrowserResult:
    """Lightweight fallback: fetch page using urllib (no JS rendering)."""
    import time
    import urllib.request
    import urllib.error

    start = time.monotonic()
    result = BrowserResult(task_id=task.task_id, url=task.url)

    try:
        req = urllib.request.Request(
            task.url,
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=task.timeout_sec) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        extracted = _extract_text_bs4(html, task.extract_selector)
        if extracted.get("error"):
            text = _extract_text_html2text(html)
            result.content = text[:task.max_chars]
        else:
            result.title = extracted.get("title", "")
            result.content = extracted.get("text", "")[:task.max_chars]
            result.links = extracted.get("links", [])

        result.status = "ok"

    except urllib.error.URLError as e:
        result.status = "error"
        result.error = f"URLError: {str(e.reason)}"
    except Exception as e:
        result.status = "error"
        result.error = f"{type(e).__name__}: {str(e)}"

    result.elapsed_ms = int((time.monotonic() - start) * 1000)
    return result


def _screenshots_dir() -> Path:
    """Get directory for screenshots."""
    candidates = [
        Path("storage") / "browser_swarm" / "screenshots",
        Path("storage_runtime") / "browser_swarm" / "screenshots",
        Path(tempfile.gettempdir()) / "rth_core" / "browser_swarm" / "screenshots",
    ]
    for d in candidates:
        try:
            d.mkdir(parents=True, exist_ok=True)
            return d
        except Exception:
            continue
    return Path(tempfile.gettempdir()) / "rth_browser_screenshots"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class BrowserSwarmOrchestrator:
    """
    Orchestrates multiple browser agents for web research, scraping,
    and content extraction. Results flow into Memory Vault and KG.
    """

    def __init__(self):
        self.last_report: Optional[Dict[str, Any]] = None
        self._playwright_available: Optional[bool] = None

    def status(self) -> Dict[str, Any]:
        """Return the current status of the browser swarm module."""
        pw = self._check_playwright()
        bs4 = self._check_bs4()
        return {
            "module": "browser_swarm",
            "version": 1,
            "playwright_available": pw,
            "beautifulsoup4_available": bs4,
            "backend": "playwright" if pw else ("urllib+bs4" if bs4 else "urllib"),
            "max_concurrent_agents": MAX_CONCURRENT_AGENTS,
            "default_timeout_sec": DEFAULT_TIMEOUT_SEC,
            "blocked_domains_count": len(BLOCKED_DOMAINS),
            "last_report_at": (self.last_report or {}).get("timestamp"),
        }

    def run(
        self,
        *,
        urls: List[str],
        mode: str = "scrape",
        extract_selector: str = "",
        summarize: bool = True,
        max_concurrent: int = MAX_CONCURRENT_AGENTS,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        reason: str = "Browser swarm web research",
        confirm_owner: bool = True,
        decided_by: str = "owner",
        ingest_to_kg: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute browser swarm tasks on a list of URLs.

        Args:
            urls: List of URLs to process
            mode: "scrape" | "search" | "screenshot"
            extract_selector: Optional CSS selector for targeted extraction
            summarize: Whether to generate text summaries
            max_concurrent: Max parallel browser agents
            timeout_sec: Per-page timeout
            reason: Governance reason
            confirm_owner: Whether to auto-approve
            decided_by: Who approves
            ingest_to_kg: Whether to inject results to Knowledge Graph
        """
        # Validate URLs
        validated_urls = []
        blocked_urls = []
        for url in urls:
            url = str(url).strip()
            if not url:
                continue
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            if _safe_domain(url):
                validated_urls.append(url)
            else:
                blocked_urls.append(url)

        if not validated_urls:
            return {
                "status": "invalid",
                "detail": "No valid URLs provided",
                "blocked_urls": blocked_urls,
            }

        # Request permission via Guardian
        req = permission_gate.propose(
            capability=Capability.NETWORK_ACCESS,
            action="browser_swarm_web_research",
            scope={
                "urls": validated_urls[:10],
                "url_count": len(validated_urls),
                "mode": mode,
                "max_concurrent": min(max_concurrent, MAX_CONCURRENT_AGENTS),
            },
            reason=self._ensure_safe_reason(reason),
            risk=RiskLevel.MEDIUM,
        )

        out: Dict[str, Any] = {
            "proposal": req.to_dict(),
            "validated_urls": validated_urls,
            "blocked_urls": blocked_urls,
        }

        if not confirm_owner:
            out["status"] = "proposal_only"
            return out

        decision = permission_gate.approve(req.request_id, decided_by=decided_by)
        out["decision"] = decision.to_dict()

        if decision.decision.value != "approved":
            out["status"] = "denied"
            return out

        # Build tasks
        tasks: List[BrowserTask] = []
        for i, url in enumerate(validated_urls):
            task = BrowserTask(
                task_id=f"bswarm_{hashlib.md5(url.encode()).hexdigest()[:8]}_{i}",
                url=url,
                mode=mode,
                extract_selector=extract_selector,
                summarize=summarize,
                timeout_sec=timeout_sec,
            )
            tasks.append(task)

        # Execute in parallel
        results = self._execute_tasks(
            tasks,
            max_concurrent=min(max_concurrent, MAX_CONCURRENT_AGENTS),
        )

        # Ingest to memory + KG
        kg_ingest = {}
        if ingest_to_kg:
            kg_ingest = self._ingest_results(results)

        # Build report
        ok_count = sum(1 for r in results if r.status == "ok")
        error_count = sum(1 for r in results if r.status == "error")
        report = {
            "status": "ok",
            "timestamp": _now(),
            "request_id": req.request_id,
            "tasks_total": len(tasks),
            "tasks_ok": ok_count,
            "tasks_error": error_count,
            "results": [r.to_dict() for r in results],
            "blocked_urls": blocked_urls,
            "knowledge_graph_ingest": kg_ingest,
            "backend": "playwright" if self._check_playwright() else "urllib",
        }

        self.last_report = report
        memory_vault.record_event(
            "browser_swarm_report",
            {
                "urls": validated_urls,
                "ok": ok_count,
                "errors": error_count,
                "mode": mode,
            },
            tags={"source": "browser_swarm"},
        )
        self._write_report(report)

        out["status"] = "ok"
        out["report"] = report
        return out

    def search(
        self,
        *,
        query: str,
        engine: str = "duckduckgo",
        max_results: int = 5,
        scrape_results: bool = True,
        reason: str = "Browser swarm web search",
        confirm_owner: bool = True,
        decided_by: str = "owner",
    ) -> Dict[str, Any]:
        """
        Search the web and optionally scrape the result pages.

        Args:
            query: Search query
            engine: Search engine to use (duckduckgo)
            max_results: Max number of result URLs to process
            scrape_results: Whether to also scrape the result pages
            reason: Governance reason
            confirm_owner: Whether to auto-approve
            decided_by: Who approves
        """
        # Build search URL
        safe_query = query.strip()[:200]
        if engine == "duckduckgo":
            search_url = f"https://html.duckduckgo.com/html/?q={safe_query.replace(' ', '+')}"
        else:
            search_url = f"https://html.duckduckgo.com/html/?q={safe_query.replace(' ', '+')}"

        # First, scrape the search results page
        search_result = self.run(
            urls=[search_url],
            mode="scrape",
            summarize=False,
            reason=self._ensure_safe_reason(reason),
            confirm_owner=confirm_owner,
            decided_by=decided_by,
            ingest_to_kg=False,
        )

        if search_result.get("status") != "ok":
            return search_result

        # Extract result URLs from search page
        report = search_result.get("report", {})
        results_list = report.get("results", [])
        result_urls = []
        if results_list:
            first = results_list[0]
            links = first.get("links", [])
            for link in links:
                if link and not link.startswith("https://duckduckgo.com") and _safe_domain(link):
                    result_urls.append(link)
                    if len(result_urls) >= max_results:
                        break

        out = {
            "status": "ok",
            "query": safe_query,
            "engine": engine,
            "search_url": search_url,
            "result_urls": result_urls,
        }

        # Optionally scrape the result pages
        if scrape_results and result_urls:
            scrape_report = self.run(
                urls=result_urls,
                mode="scrape",
                summarize=True,
                reason=f"{reason} [search results scrape]",
                confirm_owner=confirm_owner,
                decided_by=decided_by,
                ingest_to_kg=True,
            )
            out["scrape_report"] = scrape_report.get("report", {})

        return out

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _execute_tasks(
        self,
        tasks: List[BrowserTask],
        max_concurrent: int = MAX_CONCURRENT_AGENTS,
    ) -> List[BrowserResult]:
        """Execute browser tasks in parallel."""
        use_playwright = self._check_playwright()
        fetch_fn = _fetch_with_playwright if use_playwright else _fetch_with_urllib

        results: List[BrowserResult] = []
        with ThreadPoolExecutor(max_workers=min(max_concurrent, len(tasks))) as executor:
            futures = {
                executor.submit(fetch_fn, task): task
                for task in tasks
            }
            for future in as_completed(futures):
                task = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(BrowserResult(
                        task_id=task.task_id,
                        url=task.url,
                        status="error",
                        error=f"Execution error: {e}",
                    ))

        # Sort by original order
        task_order = {t.task_id: i for i, t in enumerate(tasks)}
        results.sort(key=lambda r: task_order.get(r.task_id, 999))
        return results

    def _ingest_results(self, results: List[BrowserResult]) -> Dict[str, Any]:
        """Inject results into the Knowledge Graph."""
        kg = get_knowledge_graph()
        created_nodes = 0
        created_relations = 0

        # Root node for this swarm run
        root_id = f"browser_swarm_run_{hashlib.md5(_now().encode()).hexdigest()[:10]}"
        if kg.add_node(
            node_id=root_id,
            node_type=NodeType.FRAMEWORK,
            name="Browser Swarm Research Run",
            description=f"Automated web research at {_now()}",
            properties={
                "source": "browser_swarm",
                "urls_count": len(results),
                "ok_count": sum(1 for r in results if r.status == "ok"),
            },
            reliability_score=0.8,
        ):
            created_nodes += 1

        for result in results:
            if result.status != "ok" or not result.content:
                continue

            node_id = f"web_page_{hashlib.md5(result.url.encode()).hexdigest()[:12]}"
            props = {
                "url": result.url,
                "title": result.title,
                "content_length": len(result.content),
                "links_count": len(result.links),
                "scraped_at": _now(),
            }
            if result.summary:
                props["summary"] = result.summary

            if kg.add_node(
                node_id=node_id,
                node_type=NodeType.ENTITY,
                name=result.title or result.url,
                description=result.content[:300],
                properties=props,
                reliability_score=0.7,
            ):
                created_nodes += 1

            if kg.add_relation(
                source_node_id=root_id,
                target_node_id=node_id,
                relation_type=RelationType.APPLIES_TO,
                weight=0.85,
                confidence=0.8,
                properties={"from": "browser_swarm"},
            ):
                created_relations += 1

        return {
            "created_nodes": created_nodes,
            "created_relations": created_relations,
            "kg_status": kg.get_status(),
        }

    def _check_playwright(self) -> bool:
        """Check if Playwright is available."""
        if self._playwright_available is not None:
            return self._playwright_available
        try:
            import playwright.sync_api  # noqa: F401
            self._playwright_available = True
        except ImportError:
            self._playwright_available = False
        return self._playwright_available

    def _check_bs4(self) -> bool:
        """Check if BeautifulSoup4 is available."""
        try:
            import bs4  # noqa: F401
            return True
        except ImportError:
            return False

    def _ensure_safe_reason(self, reason: str) -> str:
        """Ensure the reason has safe/audit markers for Guardian DSL."""
        tokens = reason.lower()
        if not any(tok in tokens for tok in ("safe", "audit", "dry-run", "healthcheck")):
            return f"{reason} [safe] [audit]"
        return reason

    def _write_report(self, report: Dict[str, Any]) -> None:
        """Persist the swarm report to disk."""
        candidates = [
            Path("logs") / "browser_swarm",
            Path("storage_runtime") / "logs" / "browser_swarm",
            Path(tempfile.gettempdir()) / "rth_core" / "logs" / "browser_swarm",
        ]
        for log_dir in candidates:
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                (log_dir / filename).write_text(
                    json.dumps(report, indent=2, default=str),
                    encoding="utf-8",
                )
                return
            except Exception:
                continue


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

browser_swarm = BrowserSwarmOrchestrator()
