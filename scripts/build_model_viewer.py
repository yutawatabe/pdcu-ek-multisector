"""Build and validate the standalone one-industry EK code viewer."""

from __future__ import annotations

import ast
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from ek_model import (  # noqa: E402
    compare_equivalence,
    example_primitives,
    example_trade_cost_hat,
    solve_exact_hat,
    solve_full,
)

VIEWER = ROOT / "viewer"
ANNOTATED = VIEWER / "model_annotated.py"
QUIZ = VIEWER / "quiz.json"
OUTPUT = VIEWER / "model_viewer.html"
MANIFEST = VIEWER / "manifest.json"
PRODUCTION = [
    ROOT / "src/ek_model/model.py",
    ROOT / "src/ek_model/full_solution.py",
    ROOT / "src/ek_model/exact_hat.py",
    ROOT / "src/ek_model/verification.py",
]

MATH = {
    "shares": """<math display="block"><mrow><msub><mi>π</mi><mrow><mi>n</mi><mi>i</mi></mrow></msub><mo>=</mo><mfrac><mrow><msub><mi>T</mi><mi>i</mi></msub><msup><mrow><mo>(</mo><msub><mi>w</mi><mi>i</mi></msub><msub><mi>d</mi><mrow><mi>n</mi><mi>i</mi></mrow></msub><mo>)</mo></mrow><mrow><mo>−</mo><mi>θ</mi></mrow></msup></mrow><mrow><munderover><mo>∑</mo><mi>k</mi><mi>N</mi></munderover><msub><mi>T</mi><mi>k</mi></msub><msup><mrow><mo>(</mo><msub><mi>w</mi><mi>k</mi></msub><msub><mi>d</mi><mrow><mi>n</mi><mi>k</mi></mrow></msub><mo>)</mo></mrow><mrow><mo>−</mo><mi>θ</mi></mrow></msup></mrow></mfrac></mrow></math>""",
    "price": """<math display="block"><mrow><msub><mi>P</mi><mi>n</mi></msub><mo>=</mo><mi>γ</mi><msup><mrow><mo>[</mo><munderover><mo>∑</mo><mi>i</mi><mi>N</mi></munderover><msub><mi>T</mi><mi>i</mi></msub><msup><mrow><mo>(</mo><msub><mi>w</mi><mi>i</mi></msub><msub><mi>d</mi><mrow><mi>n</mi><mi>i</mi></mrow></msub><mo>)</mo></mrow><mrow><mo>−</mo><mi>θ</mi></mrow></msup><mo>]</mo></mrow><mrow><mo>−</mo><mn>1</mn><mo>/</mo><mi>θ</mi></mrow></msup></mrow></math>""",
    "market": """<math display="block"><mrow><msub><mi>w</mi><mi>i</mi></msub><msub><mi>L</mi><mi>i</mi></msub><mo>=</mo><munderover><mo>∑</mo><mi>n</mi><mi>N</mi></munderover><msub><mi>π</mi><mrow><mi>n</mi><mi>i</mi></mrow></msub><msub><mi>w</mi><mi>n</mi></msub><msub><mi>L</mi><mi>n</mi></msub></mrow></math>""",
    "hat_shares": """<math display="block"><mrow><msubsup><mi>π</mi><mrow><mi>n</mi><mi>i</mi></mrow><mo>′</mo></msubsup><mo>=</mo><mfrac><mrow><msub><mi>π</mi><mrow><mi>n</mi><mi>i</mi></mrow></msub><msup><mrow><mo>(</mo><msub><mover><mi>w</mi><mo>^</mo></mover><mi>i</mi></msub><msub><mover><mi>d</mi><mo>^</mo></mover><mrow><mi>n</mi><mi>i</mi></mrow></msub><mo>)</mo></mrow><mrow><mo>−</mo><mi>θ</mi></mrow></msup></mrow><mrow><munderover><mo>∑</mo><mi>k</mi><mi>N</mi></munderover><msub><mi>π</mi><mrow><mi>n</mi><mi>k</mi></mrow></msub><msup><mrow><mo>(</mo><msub><mover><mi>w</mi><mo>^</mo></mover><mi>k</mi></msub><msub><mover><mi>d</mi><mo>^</mo></mover><mrow><mi>n</mi><mi>k</mi></mrow></msub><mo>)</mo></mrow><mrow><mo>−</mo><mi>θ</mi></mrow></msup></mrow></mfrac></mrow></math>""",
    "accept": """<math display="block"><mrow><mo>max</mo><mo>{</mo><msub><mi>e</mi><mtext>abs</mtext></msub><mo>,</mo><msub><mi>e</mi><mtext>rel</mtext></msub><mo>}</mo><mo>&lt;</mo><msup><mn>10</mn><mrow><mo>−</mo><mn>9</mn></mrow></msup><mo>,</mo><mspace width="1em"/><mo>and</mo><mspace width=".5em"/><mtext>all solvers converge</mtext></mrow></math>""",
}

STEPS = [
    {"id": "full_trade_system", "tab": "full", "title": "1. Trade shares and prices", "scope": "derived at each wage guess", "color": "green", "summary": "Construct delivered costs with importer rows and exporter columns, then normalize competitiveness within each importer.", "math": MATH["shares"]},
    {"id": "full_residual", "tab": "full", "title": "2. Levels market-clearing residual", "scope": "solver residual", "color": "pink", "summary": "Compare each exporter's labor income with revenue collected from every importer. The residual is zero only at equilibrium.", "math": MATH["market"]},
    {"id": "full_solver", "tab": "full", "title": "3. Full equilibrium solver", "scope": "country 0 fixed exactly", "color": "blue", "summary": "Fix wage 0 at one, solve the other log wages, and certify every country's market residual after optimization.", "math": MATH["accept"]},
    {"id": "hat_inputs", "tab": "hat", "title": "1. Baseline sufficient statistics", "scope": "fixed across the hat solve", "color": "amber", "summary": "Carry baseline bilateral shares and incomes into the counterfactual; technology levels need not be recovered.", "math": ""},
    {"id": "hat_shares_prices", "tab": "hat", "title": "2. Counterfactual shares and prices", "scope": "derived at each wage-hat guess", "color": "green", "summary": "Reweight every baseline share by its delivered-cost change and renormalize within importer rows.", "math": MATH["hat_shares"]},
    {"id": "hat_residual", "tab": "hat", "title": "3. Hat market-clearing residual", "scope": "solver residual", "color": "pink", "summary": "Scale baseline incomes by wage hats and require the resulting exporter income to equal counterfactual sales.", "math": MATH["market"]},
    {"id": "hat_solver", "tab": "hat", "title": "4. Exact-hat solver", "scope": "wage hat 0 fixed exactly", "color": "blue", "summary": "Solve the independent hat residuals and retain the full residual norm as evidence of convergence.", "math": MATH["accept"]},
    {"id": "test_routes", "tab": "test", "title": "1. Run both counterfactual routes", "scope": "E0 → E1", "color": "purple", "summary": "Solve the baseline and shocked economies in levels, then solve the identical shock from the baseline in exact changes.", "math": ""},
    {"id": "test_compare", "tab": "test", "title": "2. Compare and certify", "scope": "pre-specified acceptance test", "color": "teal", "summary": "Compare wages, price indices, bilateral shares, and real wages; execution alone is never treated as equivalence.", "math": MATH["accept"]},
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def annotated_snippets() -> dict[str, dict[str, object]]:
    source = ANNOTATED.read_text(encoding="utf-8")
    compile(source, str(ANNOTATED), "exec")
    tree = ast.parse(source)
    lines = source.splitlines()
    annotations: list[tuple[str, int]] = []
    for index, line in enumerate(lines, start=1):
        match = re.match(r"\s*#\s*@step:(\S+)", line)
        if match:
            annotations.append((match.group(1), index))
    functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    snippets: dict[str, dict[str, object]] = {}
    for step_id, annotation_line in annotations:
        function = next((node for node in functions if node.lineno > annotation_line), None)
        if function is None or function.end_lineno is None:
            raise ValueError(f"No function follows annotation {step_id}")
        snippets[step_id] = {
            "function": function.name,
            "start": function.lineno,
            "end": function.end_lineno,
            "code": "\n".join(lines[function.lineno - 1 : function.end_lineno]),
        }
    expected = {step["id"] for step in STEPS}
    if set(snippets) != expected:
        raise ValueError(f"Annotation mismatch: expected {expected}, found {set(snippets)}")
    return snippets


def verification() -> dict[str, object]:
    primitives = example_primitives()
    shock = example_trade_cost_hat()
    baseline = solve_full(primitives)
    counterfactual = solve_full(primitives.with_trade_cost_hat(shock))
    hats = solve_exact_hat(primitives, baseline, shock)
    certificate = compare_equivalence(baseline, counterfactual, hats).as_dict()
    certificate["fixture"] = {
        "countries": primitives.countries,
        "theta": primitives.theta,
        "shock": "10% symmetric trade-cost cut between countries 0 and 1",
    }
    if not certificate["passed"]:
        raise RuntimeError(f"Cannot build a passing viewer from failed evidence: {certificate}")
    return certificate


def build_html(snippets: dict[str, object], certificate: dict[str, object], quiz: list[object]) -> str:
    payloads = {
        "__STEPS__": json.dumps(STEPS, ensure_ascii=False).replace("</", "<\\/"),
        "__SNIPPETS__": json.dumps(snippets, ensure_ascii=False).replace("</", "<\\/"),
        "__CERTIFICATE__": json.dumps(certificate, ensure_ascii=False).replace("</", "<\\/"),
        "__QUIZ__": json.dumps(quiz, ensure_ascii=False).replace("</", "<\\/"),
        "__SHARES__": MATH["shares"],
        "__PRICE__": MATH["price"],
        "__MARKET__": MATH["market"],
    }
    html = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>One-industry Eaton–Kortum PDCU code viewer</title>
<style>
:root{--ink:#172033;--muted:#617086;--line:#dce3eb;--paper:#f7f8fb;--card:#fff;--blue:#3276b1;--green:#4b8f37;--pink:#bb4b72;--amber:#ad741d;--purple:#7567c7;--teal:#17856b;--shadow:0 12px 32px #1c335018}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 Inter,ui-sans-serif,system-ui,sans-serif}header{background:linear-gradient(125deg,#14243b,#214f68);color:#fff;padding:38px 24px}header .wrap,.container{max-width:1180px;margin:auto}h1{font-size:clamp(28px,4vw,46px);line-height:1.08;margin:0 0 10px}header p{max-width:800px;color:#d9e6ed;margin:0}.badge{display:inline-block;background:#dff6ed;color:#07513e;padding:4px 10px;border-radius:99px;font-weight:700;margin-bottom:14px}.container{padding:26px 20px 60px}.section{background:var(--card);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:24px;margin-bottom:24px}.section-title{font-size:24px;margin:0 0 6px}.sub{color:var(--muted);margin:0 0 20px}.context-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.context-card,.life-card{border:1px solid var(--line);border-radius:13px;padding:16px;background:#fbfcfe}.context-card h3,.life-card h3{margin:0 0 8px;font-size:16px}.equation{overflow:auto;padding:8px 0;min-height:76px}math{font-size:1.05rem}.index-strip{display:flex;gap:10px;flex-wrap:wrap;margin:15px 0}.index{border-radius:9px;padding:7px 11px;font-weight:700}.importer{background:#e6f1fb;color:#0c447c}.exporter{background:#eaf3de;color:#27500a}.lifecycle{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}.route{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:14px;background:#f2f6fa;border-radius:14px;padding:16px;margin-top:16px}.route-box{background:white;border:1px solid var(--line);border-radius:10px;padding:13px}.route-arrow{font-size:26px;color:var(--blue)}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}.tab{border:1px solid var(--line);background:#f4f6f9;color:var(--ink);padding:9px 14px;border-radius:9px;font-weight:700;cursor:pointer}.tab.active{background:#203f59;color:white;border-color:#203f59}.stage{border:1px solid var(--line);border-left:5px solid var(--stage);border-radius:13px;margin:11px 0;overflow:hidden}.stage-head{width:100%;border:0;background:white;padding:16px;text-align:left;cursor:pointer;color:inherit}.stage-head:hover{background:#f9fbfd}.stage-title{display:flex;justify-content:space-between;gap:15px;font-weight:800}.scope{color:var(--muted);font-size:13px}.summary{margin:6px 0 0;color:#3d4b60}.stage-body{display:none;border-top:1px solid var(--line);background:#f8fafc;padding:15px}.stage.open .stage-body{display:block}.step-equation{background:white;border:1px solid var(--line);border-radius:10px;padding:8px;margin-bottom:12px;overflow:auto}pre{margin:0;overflow:auto;background:#121b2a;color:#e7edf5;border-radius:10px;padding:16px;font:13px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace}.certificate{width:100%;border-collapse:collapse}.certificate th,.certificate td{border-bottom:1px solid var(--line);padding:10px;text-align:right}.certificate th:first-child,.certificate td:first-child{text-align:left}.pass{color:#087352;font-weight:800}.fail{color:#b42318;font-weight:800}.diag-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:16px}.diag{border:1px solid var(--line);border-radius:10px;padding:13px}.mechanism{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:20px 0}.mechanism span{background:#edf3f7;border-radius:8px;padding:8px 10px;font-weight:700}.mechanism b{color:var(--blue)}.quiz-item{border-top:1px solid var(--line);padding:18px 0}.quiz-item label{display:block;margin:7px 0}.quiz-item input[type=text]{width:100%;padding:10px;border:1px solid #bfc9d6;border-radius:8px}.feedback{display:none;background:#f2f6fa;border-radius:9px;padding:10px;margin-top:9px}.quiz-result{font-size:18px;font-weight:800;margin-left:12px}@media(max-width:800px){.context-grid,.lifecycle,.diag-grid{grid-template-columns:1fr}.route{grid-template-columns:1fr}.route-arrow{transform:rotate(90deg);justify-self:center}.section{padding:18px}.certificate{font-size:12px}.certificate th,.certificate td{padding:7px 4px}}
</style></head><body>
<header><div class="wrap"><div class="badge">PDCU · Understand</div><h1>One-industry Eaton–Kortum<br>from equations to executable evidence</h1><p>The full-level and exact-hat routes solve the same counterfactual. Expand each step to see the reader-oriented implementation, then inspect the generated certificate before taking the quiz.</p></div></header>
<main class="container">
<section class="section"><h2 class="section-title">What is being solved</h2><p class="sub">Technology, labor, trade costs, and elasticity are fixed. Relative wages clear goods markets; prices and shares are derived at each wage guess.</p>
<div class="index-strip"><span class="index importer">n · importer · row</span><span class="index exporter">i · exporter · column</span><span class="index">w₀ = 1 · exact numeraire</span></div>
<div class="context-grid"><article class="context-card"><h3>Bilateral expenditure shares</h3><div class="equation">__SHARES__</div><p>Each importer row sums to one exactly.</p></article><article class="context-card"><h3>Price index</h3><div class="equation">__PRICE__</div><p>Computed from the same competitiveness denominator.</p></article><article class="context-card"><h3>Equilibrium closure</h3><div class="equation">__MARKET__</div><p>Residuals approach zero only when the solver converges.</p></article></div>
<div class="lifecycle"><article class="life-card"><h3>Fixed</h3><p>T, L, d, θ and the country-0 numeraire.</p></article><article class="life-card"><h3>Solver unknown</h3><p>Log wages for countries 1…N−1.</p></article><article class="life-card"><h3>Warm state</h3><p>None is carried between E⁰, E¹, and hats.</p></article><article class="life-card"><h3>Derived</h3><p>Shares, prices, income, welfare, and full residuals.</p></article></div>
<div class="route"><div class="route-box"><strong>Levels route</strong><br>E⁰ = solve(T,L,d) → E¹ = solve(T,L,d′) → E¹/E⁰</div><div class="route-arrow">⇄</div><div class="route-box"><strong>Exact-hat route</strong><br>(π⁰,Y⁰) + d̂ → solve ŵ → (π′,P̂,ŵ/P̂)</div></div></section>
<section class="section"><h2 class="section-title">Read the code as a solution hierarchy</h2><p class="sub">Descriptions remain visible before expansion. One click reveals the corresponding function body directly.</p><div id="tabs" class="tabs"></div><div id="algorithm"></div></section>
<section class="section"><h2 class="section-title">Verification certificate</h2><p class="sub">Generated by running the reviewed production solvers during the viewer build.</p><div id="certificate"></div><div id="diagnostics" class="diag-grid"></div>
<div class="mechanism"><span>d₀₁,d₁₀ ↓</span><b>→</b><span>delivered costs ↓</span><b>→</b><span>trade shares shift</span><b>→</b><span>export demand and wages adjust</span><b>→</b><span>P changes</span><b>→</b><span>w/P changes</span></div></section>
<section class="section"><h2 class="section-title">Understanding quiz</h2><p class="sub">Answers stay in this browser session. Feedback explains the model concept, not Python syntax.</p><div id="quiz"></div><button class="tab active" id="submit-quiz">Check answers</button><span id="quiz-result" class="quiz-result"></span></section>
</main>
<script>
const STEPS=__STEPS__;const SNIPPETS=__SNIPPETS__;const CERT=__CERTIFICATE__;const QUIZ=__QUIZ__;const COLORS={green:'#4b8f37',pink:'#bb4b72',blue:'#3276b1',amber:'#ad741d',purple:'#7567c7',teal:'#17856b'};let activeTab='full';let openStep=null;
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
function renderTabs(){const labels={full:'Full solution',hat:'Exact hat',test:'Equivalence test'};document.getElementById('tabs').innerHTML=Object.entries(labels).map(([id,label])=>`<button class="tab ${activeTab===id?'active':''}" data-tab="${id}">${label}</button>`).join('');document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{activeTab=b.dataset.tab;openStep=null;renderTabs();renderAlgorithm()})}
function renderAlgorithm(){document.getElementById('algorithm').innerHTML=STEPS.filter(s=>s.tab===activeTab).map(s=>{const open=openStep===s.id;const source=SNIPPETS[s.id];return `<article class="stage ${open?'open':''}" style="--stage:${COLORS[s.color]}"><button class="stage-head" data-step="${s.id}"><div class="stage-title"><span>${esc(s.title)}</span><span>${open?'−':'+'}</span></div><div class="scope">${esc(s.scope)} · ${esc(source.function)} · lines ${source.start}–${source.end}</div><p class="summary">${esc(s.summary)}</p></button><div class="stage-body">${s.math?`<div class="step-equation">${s.math}</div>`:''}<pre><code>${esc(source.code)}</code></pre></div></article>`}).join('');document.querySelectorAll('[data-step]').forEach(b=>b.onclick=()=>{openStep=openStep===b.dataset.step?null:b.dataset.step;renderAlgorithm()})}
function fmt(x){return Number(x).toExponential(3)}
function renderCertificate(){const rows=Object.entries(CERT.comparisons).map(([name,c])=>`<tr><td>${esc(name.replaceAll('_',' '))}</td><td>${fmt(c.max_absolute_error)}</td><td>${fmt(c.max_relative_error)}</td><td>${fmt(c.tolerance)}</td><td class="${c.passed?'pass':'fail'}">${c.passed?'PASS':'FAIL'}</td></tr>`).join('');document.getElementById('certificate').innerHTML=`<table class="certificate"><thead><tr><th>Object</th><th>Max absolute</th><th>Max relative</th><th>Tolerance</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table>`;document.getElementById('diagnostics').innerHTML=Object.entries(CERT.solver_diagnostics).map(([name,d])=>`<article class="diag"><strong>${esc(name.replaceAll('_',' '))}</strong><div class="${d.converged?'pass':'fail'}">${d.converged?'Converged':'Not converged'}</div><div>‖F‖∞ = ${fmt(d.residual_norm)}</div><div>${d.evaluations} evaluations</div></article>`).join('')}
function renderQuiz(){document.getElementById('quiz').innerHTML=QUIZ.map((q,index)=>`<article class="quiz-item" data-q="${q.id}"><strong>${index+1}. ${esc(q.prompt)}</strong>${q.type==='choice'?q.choices.map((choice,i)=>`<label><input type="radio" name="${q.id}" value="${i}"> ${esc(choice)}</label>`).join(''):`<input type="text" aria-label="Answer ${index+1}" placeholder="Explain in your own words">`}<div class="feedback"></div></article>`).join('')}
function checkQuiz(){let score=0;QUIZ.forEach(q=>{const item=document.querySelector(`[data-q="${q.id}"]`);let correct=false;if(q.type==='choice'){const selected=item.querySelector('input:checked');correct=!!selected&&Number(selected.value)===q.answer}else{const value=item.querySelector('input[type=text]').value.toLowerCase();correct=q.keywords.every(k=>value.includes(k.toLowerCase()))}if(correct)score++;const feedback=item.querySelector('.feedback');feedback.style.display='block';feedback.innerHTML=`<strong class="${correct?'pass':'fail'}">${correct?'Correct':'Review this'}</strong><br>${esc(q.answer_text||q.choices[q.answer])}<br><span>${esc(q.explanation)}</span>`});document.getElementById('quiz-result').textContent=`${score} / ${QUIZ.length}`}
renderTabs();renderAlgorithm();renderCertificate();renderQuiz();document.getElementById('submit-quiz').onclick=checkQuiz;
</script></body></html>'''
    for marker, value in payloads.items():
        html = html.replace(marker, value)
    return html


class _HTMLCheck(HTMLParser):
    pass


def main() -> None:
    snippets = annotated_snippets()
    quiz = json.loads(QUIZ.read_text(encoding="utf-8"))
    if len(quiz) != 8 or len({item["id"] for item in quiz}) != 8:
        raise ValueError("Quiz must contain eight unique questions")
    certificate = verification()
    html = build_html(snippets, certificate, quiz)
    if "$$" in html or "&#x20;" in html:
        raise ValueError("Unrendered mathematics or leaked entity found")
    parser = _HTMLCheck()
    parser.feed(html)
    for step in STEPS:
        if step["id"] not in html:
            raise ValueError(f"Missing expansion target {step['id']}")
    OUTPUT.write_text(html, encoding="utf-8")

    source_hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path) for path in PRODUCTION}
    combined = hashlib.sha256("".join(source_hashes[key] for key in sorted(source_hashes)).encode()).hexdigest()
    manifest = {
        "viewer_design": "equation-first-expandable-code-tree",
        "production_sha256": combined,
        "production_source_sha256": source_hashes,
        "production_code_modified_for_viewer": False,
        "annotated_code_role": "explanatory reconstruction mapped to production source",
        "reader_to_production": {
            "derive_trade_shares_and_prices": "ek_model.model.trade_system",
            "build_levels_market_residual": "ek_model.model.normalized_market_residual",
            "full_solution_route": "ek_model.full_solution.solve_full",
            "derive_hat_shares_and_prices": "ek_model.exact_hat.solve_exact_hat.implied_objects",
            "build_hat_market_residual": "ek_model.exact_hat.solve_exact_hat.residual",
            "exact_hat_route": "ek_model.exact_hat.solve_exact_hat",
            "run_both_counterfactual_routes": "tests.test_exact_hat_equivalence",
            "certify_equivalence": "ek_model.verification.compare_equivalence",
        },
        "outputs": ["model_viewer.html", "model_annotated.py", "quiz.json", "manifest.json"],
        "step_count": len(STEPS),
        "flow_group_count": 3,
        "math_node_count": html.count("<math"),
        "verification_passed": certificate["passed"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Built {OUTPUT.relative_to(ROOT)} with {len(STEPS)} expandable steps")
    print(json.dumps(certificate, indent=2))


if __name__ == "__main__":
    main()
