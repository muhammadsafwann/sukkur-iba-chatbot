"""
api.py

FastAPI application that serves FAQ search via POST /api/search.
Supports both retrieval‑only and generative (LLM‑based) answers.
Run with: uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
"""

import os
import time
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from html import escape  # FIX: escape user query text to prevent stored XSS
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import List, Optional

from src.vector_store import VectorStore
from src.generator import AnswerGenerator
from src.analytics import log_query, get_stats, get_daily_counts

# ----------------------------------------------------------------------
# Global dependencies
store = None
generator = None
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    global store, generator
    print(">> Loading vector store...")
    store = await asyncio.to_thread(VectorStore)
    if not os.path.exists("faiss_index_combined.bin") or not os.path.exists("documents_combined.pkl"):
        print("WARNING: FAISS index or documents missing! Please run build_index.py first.")
    else:
        store.load("faiss_index_combined.bin", "documents_combined.pkl")
        print(f"OK: Vector store ready with {store.index.ntotal} vectors.")

    print(">> Loading answer generator...")
    generator = AnswerGenerator()
    print("OK: Answer generator ready.")
    yield
    print("STOP: Shutting down. Cleaning up resources...")
    store = None
    generator = None

# ----------------------------------------------------------------------
# FastAPI app
app = FastAPI(
    title="University FAQ RAG API",
    description="Semantic search over Sukkur IBA FAQ dataset and prospectus",
    version="1.0.0",
    lifespan=lifespan
)

# Session middleware (must be before CORS and routing)
SECRET_KEY = os.environ.get("SESSION_SECRET", "dev-secret-change-me")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# CORS
frontend_url = os.environ.get("FRONTEND_URL", "*")
origins = [origin.strip() for origin in frontend_url.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files from backend/static folder
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    print(f"Warning: Static directory not found at {static_dir}")

# ----------------------------------------------------------------------
# Request/response models
class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    use_llm: Optional[bool] = True

class SearchResult(BaseModel):
    id: str
    question: str
    answer: str
    department: str
    tags: str
    score: float

class SearchResponse(BaseModel):
    success: bool
    results: List[SearchResult]

# ----------------------------------------------------------------------
# API endpoints
@app.post("/api/search", response_model=SearchResponse)
def search(request: SearchRequest):
    try:
        log_query(request.query)
        results = store.search(request.query, k=request.top_k)

        if request.use_llm and results:
            answer = generator.generate(request.query, results)
            negative_phrases = [
                "don't have that information", "i don't know", "no mention",
                "does not specify", "not provided", "cannot find",
                "unable to locate", "does not contain", "not mentioned"
            ]
            if any(phrase in answer.lower() for phrase in negative_phrases):
                best = results[0]
                answer = best['answer']
            return {
                "success": True,
                "results": [{
                    "id": "0",
                    "question": request.query,
                    "answer": answer,
                    "department": "Generated",
                    "tags": "",
                    "score": 1.0
                }]
            }
        else:
            return {
                "success": True,
                "results": [
                    {
                        "id": str(r["id"]),
                        "question": r["question"],
                        "answer": r["answer"],
                        "department": r["department"],
                        "tags": r["tags"] or "",
                        "score": r["score"],
                    } for r in results
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------
# Admin authentication (session‑based)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

def require_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin/login", status_code=303)
    return True

@app.get("/admin/login", response_class=HTMLResponse)
def login_form():
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head><title>Admin Login</title>
    <style>
        body { background:#F8FAFC; font-family:Inter,sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; margin:0; }
        .login-box { background:white; padding:2rem; border-radius:1rem; box-shadow:0 4px 6px -1px rgba(0,0,0,0.1); width:320px; text-align:center; border:1px solid #E2E8F0; }
        h2 { color:#4F46E5; margin-bottom:1.5rem; }
        input { width:100%; padding:0.75rem; margin:0.5rem 0; border:1px solid #CBD5E1; border-radius:0.5rem; font-size:1rem; }
        button { background:#6366F1; color:white; border:none; padding:0.75rem 1.5rem; border-radius:0.5rem; font-size:1rem; cursor:pointer; width:100%; margin-top:1rem; }
        button:hover { background:#4F46E5; }
        .error { color:#EF4444; margin-top:1rem; font-size:0.875rem; }
    </style>
    </head>
    <body>
        <div class="login-box"><h2>Admin Login</h2>
        <form method="post" action="/admin/login"><input type="password" name="password" placeholder="Enter admin password" required autofocus><button type="submit">Login</button></form></div>
    </body>
    </html>
    """)

@app.post("/admin/login")
async def login(request: Request):
    form = await request.form()
    password = form.get("password")
    if password == ADMIN_PASSWORD:
        request.session["admin_logged_in"] = True
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head><title>Admin Login</title>
    <style>body { background:#F8FAFC; font-family:Inter,sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; margin:0; }
    .login-box { background:white; padding:2rem; border-radius:1rem; box-shadow:0 4px 6px -1px rgba(0,0,0,0.1); width:320px; text-align:center; border:1px solid #E2E8F0; }
    h2 { color:#4F46E5; margin-bottom:1.5rem; }
    input { width:100%; padding:0.75rem; margin:0.5rem 0; border:1px solid #CBD5E1; border-radius:0.5rem; font-size:1rem; }
    button { background:#6366F1; color:white; border:none; padding:0.75rem 1.5rem; border-radius:0.5rem; font-size:1rem; cursor:pointer; width:100%; margin-top:1rem; }
    button:hover { background:#4F46E5; }
    .error { color:#EF4444; margin-top:1rem; font-size:0.875rem; }</style>
    </head>
    <body>
        <div class="login-box"><h2>Admin Login</h2>
        <form method="post" action="/admin/login"><input type="password" name="password" placeholder="Enter admin password" required><button type="submit">Login</button></form>
        <div class="error">Invalid password. Please try again.</div></div>
    </body>
    </html>
    """, status_code=401)

@app.get("/admin/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login")

@app.get("/admin/stats")
def admin_stats(request: Request, _=Depends(require_admin)):
    return get_stats()

@app.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request, _=Depends(require_admin)):
    stats = get_stats()

    # FIX: Use get_daily_counts() which queries the full database with SQL
    # aggregation — never capped at 100.  The old approach iterated over
    # stats['recent'] (limited to 100 rows), so any day with more than 100
    # total queries across the window would produce silently wrong numbers.
    day_counts_map = get_daily_counts(days=7)

    # Build ordered labels and counts for the last 7 days
    last_7_days = []
    counts = []
    for i in range(6, -1, -1):
        day = time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
        last_7_days.append(day)
        counts.append(day_counts_map.get(day, 0))

    # FIX: Guard against all-zero week so "most active day" is not misleading
    most_active_count = max(counts) if counts else 0
    most_active_day = (
        last_7_days[counts.index(most_active_count)]
        if most_active_count > 0 else "—"
    )

    # Build the recent-queries table rows.
    # FIX: escape() prevents stored XSS from user-supplied query text.
    # Each row now shows a row number, a clean timestamp, and the full
    # query text that wraps instead of being silently truncated.
    recent_rows = ""
    for i, entry in enumerate(stats["recent"][:20], start=1):
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry["timestamp"]))
        query_text = escape(entry["query"])
        row_bg = "#F8FAFC" if i % 2 == 0 else "white"
        recent_rows += f"""
            <tr style="background:{row_bg};">
                <td class="col-num">{i}</td>
                <td class="col-ts">{ts}</td>
                <td class="col-query">{query_text}</td>
            </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Chatbot Analytics | Sukkur IBA</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ background: #F8FAFC; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding: 2rem; color: #0F172A; }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            .header {{ margin-bottom: 2rem; }}
            .header h1 {{ font-size: 1.8rem; font-weight: 700; color: #4F46E5; display: flex; align-items: center; gap: 0.5rem; }}
            .header h1 img {{ width: 32px; height: 32px; }}
            .header p {{ color: #64748B; margin-top: 0.25rem; }}
            .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }}
            .card {{ background: white; border-radius: 1rem; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03); transition: all 0.2s ease; border: 1px solid #E2E8F0; }}
            .card:hover {{ box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.025); }}
            .card-title {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: #64748B; margin-bottom: 0.5rem; }}
            .card-value {{ font-size: 2.5rem; font-weight: 700; color: #0F172A; line-height: 1.2; }}
            .card-sub {{ font-size: 0.75rem; color: #94A3B8; margin-top: 0.5rem; }}
            .two-columns {{ display: grid; grid-template-columns: 1fr 1.5fr; gap: 1.5rem; margin-bottom: 2rem; }}
            .chart-card, .table-card {{ background: white; border-radius: 1rem; border: 1px solid #E2E8F0; padding: 1.25rem; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }}
            .section-title {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; color: #1E293B; display: flex; align-items: center; gap: 0.5rem; }}
            .section-title img {{ width: 22px; height: 22px; }}
            canvas {{ max-height: 280px; width: 100%; }}

            /* Recent queries table */
            .recent-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; table-layout: fixed; }}
            .recent-table thead tr {{ background: #F1F5F9; }}
            .recent-table th {{
                text-align: left;
                padding: 0.7rem 0.75rem;
                border-bottom: 2px solid #E2E8F0;
                color: #475569;
                font-weight: 600;
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.04em;
            }}
            .recent-table td {{
                padding: 0.65rem 0.75rem;
                border-bottom: 1px solid #F1F5F9;
                color: #1E293B;
                vertical-align: top;
            }}
            .recent-table tr:last-child td {{ border-bottom: none; }}
            .recent-table tr:hover td {{ background: #EFF6FF !important; }}
            /* Column widths */
            .col-num  {{ width: 3rem; text-align: center; color: #94A3B8; font-size: 0.78rem; }}
            .col-ts   {{ width: 11rem; font-family: monospace; font-size: 0.78rem; color: #64748B; white-space: nowrap; }}
            .col-query {{
                /* Allow query text to wrap fully — no silent truncation */
                word-break: break-word;
                white-space: normal;
                color: #1E293B;
                line-height: 1.5;
            }}
            .table-footer {{
                margin-top: 0.75rem;
                font-size: 0.7rem;
                color: #94A3B8;
                text-align: right;
            }}

            @media (max-width: 768px) {{
                body {{ padding: 1rem; }}
                .two-columns {{ grid-template-columns: 1fr; }}
                .stats-grid {{ grid-template-columns: 1fr; }}
                .col-ts {{ width: auto; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>
                    <img src="/static/analysis.png" alt="analysis">
                    Analytics Dashboard
                </h1>
                <p>Real‑time query insights for Sukkur IBA FAQ Chatbot</p>
            </div>

            <div class="stats-grid">
                <div class="card">
                    <div class="card-title">Total Queries</div>
                    <div class="card-value">{stats['total']}</div>
                    <div class="card-sub">Since launch</div>
                </div>
                <div class="card">
                    <div class="card-title">Last 7 Days</div>
                    <div class="card-value">{sum(counts)}</div>
                    <div class="card-sub">Queries</div>
                </div>
                <div class="card">
                    <div class="card-title">Most Active Day</div>
                    <div class="card-value">{most_active_count}</div>
                    <div class="card-sub">{most_active_day}</div>
                </div>
            </div>

            <div class="two-columns">
                <div class="chart-card">
                    <div class="section-title">
                        <img src="/static/calender.png" alt="calendar">
                        Daily queries (last 7 days)
                    </div>
                    <canvas id="dailyChart"></canvas>
                </div>
                <div class="table-card">
                    <div class="section-title">
                        <img src="/static/clock.png" alt="clock">
                        Recent queries
                    </div>
                    <div style="overflow-x: auto;">
                        <table class="recent-table">
                            <thead>
                                <tr>
                                    <th class="col-num">#</th>
                                    <th class="col-ts">Timestamp</th>
                                    <th class="col-query">Query</th>
                                </tr>
                            </thead>
                            <tbody>
                                {recent_rows}
                            </tbody>
                        </table>
                    </div>
                    <div class="table-footer">
                        Showing last {min(20, len(stats['recent']))} of {stats['total']} queries
                    </div>
                </div>
            </div>
        </div>

        <script>
            const ctx = document.getElementById('dailyChart').getContext('2d');
            new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: {last_7_days},
                    datasets: [{{
                        label: 'Queries',
                        data: {counts},
                        backgroundColor: '#6366F1',
                        borderRadius: 6,
                        barPercentage: 0.65,
                        categoryPercentage: 0.8,
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{ backgroundColor: '#0F172A', titleColor: '#F8FAFC', bodyColor: '#CBD5E1' }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            grid: {{ color: '#E2E8F0' }},
                            ticks: {{ stepSize: 1, precision: 0 }}
                        }},
                        x: {{
                            grid: {{ display: false }},
                            ticks: {{ autoSkip: true, maxRotation: 45, minRotation: 30 }}
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

# ----------------------------------------------------------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "vectors": store.index.ntotal,
        "documents": len(store.documents)
    }