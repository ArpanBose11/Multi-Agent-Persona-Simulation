import os
import json
import random
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allow HTML frontend to call this API

# ─────────────────────────────────────────────
# SEGMENT-AWARE PERSONA GENERATION
# ─────────────────────────────────────────────

SEGMENT_PROFILES = {
    "Urban Commuter":     {"income": [40000,90000],  "ps": [0.3,0.5], "bt": [0.5,0.8], "ra": [0.2,0.5], "ca": [0.5,0.9], "rt": [0.4,0.7], "age": [25,40]},
    "Student":            {"income": [5000,20000],   "ps": [0.7,1.0], "bt": [0.3,0.6], "ra": [0.4,0.7], "ca": [0.2,0.5], "rt": [0.5,0.9], "age": [18,24]},
    "Gig Rider":          {"income": [15000,35000],  "ps": [0.6,0.9], "bt": [0.3,0.6], "ra": [0.6,0.9], "ca": [0.3,0.6], "rt": [0.3,0.6], "age": [22,35]},
    "Eco Conscious":      {"income": [50000,120000], "ps": [0.2,0.5], "bt": [0.6,0.9], "ra": [0.1,0.4], "ca": [0.6,1.0], "rt": [0.5,0.8], "age": [28,50]},
    "Price Sensitive":    {"income": [10000,30000],  "ps": [0.8,1.0], "bt": [0.2,0.5], "ra": [0.5,0.8], "ca": [0.1,0.4], "rt": [0.1,0.4], "age": [30,50]},
    "Suburban Family":    {"income": [35000,80000],  "ps": [0.4,0.7], "bt": [0.5,0.8], "ra": [0.5,0.8], "ca": [0.4,0.7], "rt": [0.2,0.5], "age": [32,50]},
    "Tech Early Adopter": {"income": [60000,150000], "ps": [0.1,0.4], "bt": [0.4,0.7], "ra": [0.1,0.3], "ca": [0.6,1.0], "rt": [0.7,1.0], "age": [22,38]},
    "Rural Buyer":        {"income": [8000,25000],   "ps": [0.7,1.0], "bt": [0.4,0.7], "ra": [0.7,1.0], "ca": [0.0,0.2], "rt": [0.1,0.3], "age": [25,55]},
}

def generate_personas(n=40, seed=42):
    random.seed(seed)
    segments = list(SEGMENT_PROFILES.keys())
    personas = []
    for i in range(n):
        seg = segments[i % len(segments)]
        p = SEGMENT_PROFILES[seg]
        personas.append({
            "persona_id": i + 1,
            "segment": seg,
            "age": random.randint(*p["age"]),
            "monthly_income": round(random.uniform(*p["income"]) / 1000) * 1000,
            "price_sensitivity": round(random.uniform(*p["ps"]), 2),
            "brand_trust": round(random.uniform(*p["bt"]), 2),
            "range_anxiety": round(random.uniform(*p["ra"]), 2),
            "charging_access": round(random.uniform(*p["ca"]), 2),
            "risk_tolerance": round(random.uniform(*p["rt"]), 2),
        })
    return personas

# ─────────────────────────────────────────────
# DECISION ENGINE
# ─────────────────────────────────────────────

def compute_decision(persona, scenario):
    annual = persona["monthly_income"] * 12
    affordability = max(0, min(1, 1 - scenario["price"] / annual))
    emi_pressure = max(0, min(1, 1 - scenario["emi"] / persona["monthly_income"]))
    competitor_threat = max(0, min(1, (scenario["price"] - scenario["competitor_price"]) / scenario["competitor_price"]))
    practicality = max(0, min(1, scenario["range"] / (100 + persona["range_anxiety"] * 50)))

    score = (affordability * 0.30 + emi_pressure * 0.15 + practicality * 0.20
             + (1 - competitor_threat) * 0.20 + persona["brand_trust"] * 0.10
             + persona["risk_tolerance"] * 0.05)
    score *= (1 - persona["price_sensitivity"] * 0.3)

    decision = "Buy" if score >= 0.60 else "Switch" if competitor_threat >= 0.65 else "Delay"

    factors = {
        "PRICE_SENSITIVE": 1 - affordability,
        "RANGE_ANXIETY": 1 - practicality,
        "COMPETITOR_THREAT": competitor_threat,
        "INFRA_DEPENDENT": 1 - persona["charging_access"],
        "EMI_STRESS": 1 - emi_pressure,
    }
    sorted_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)

    return {
        "decision": decision,
        "confidence": round(score, 3),
        "primary_reason_code": sorted_factors[0][0],
        "secondary_reason_code": sorted_factors[1][0],
        "affordability_score": round(affordability, 3),
        "practicality_score": round(practicality, 3),
        "competitor_attractiveness": round(competitor_threat, 3),
        "infrastructure_dependency_score": round(1 - persona["charging_access"], 3),
        "price_elasticity_signal": round(-persona["price_sensitivity"] + 0.5, 3),
        "emi_pressure_score": round(1 - emi_pressure, 3),
    }

# ─────────────────────────────────────────────
# LLM RATIONALE (real CrewAI call)
# ─────────────────────────────────────────────

def get_llm_rationale(persona, scenario, decision):
    """Call actual CrewAI agent for human-like reasoning."""
    try:
        from crewai import Task, Crew
        from agents.decision_agent import decision_agent

        prompt = f"""
You are a {persona['age']}-year-old {persona['segment']} in India.
Monthly income: ₹{persona['monthly_income']:,}.
An EV costs ₹{scenario['price']:,} (EMI ₹{scenario['emi']:,}/month), range {scenario['range']}km.
Competitor price: ₹{scenario['competitor_price']:,}.
Decision: {decision}

Write ONE sentence (max 20 words) in first person explaining why you made this decision.
Be specific to your life situation. Return ONLY the sentence.
"""
        task = Task(description=prompt, expected_output="One sentence rationale", agent=decision_agent)
        crew = Crew(agents=[decision_agent], tasks=[task])
        result = crew.kickoff()
        return str(result).strip().strip('"')

    except Exception as e:
        # Fallback if CrewAI not available
        fallbacks = {
            "Buy": f"The EMI fits my ₹{persona['monthly_income']:,} income and the range covers my daily needs.",
            "Delay": f"I'll wait for better charging infrastructure before committing ₹{scenario['price']:,}.",
            "Switch": f"The competitor at ₹{scenario['competitor_price']:,} offers better value for my situation.",
        }
        return fallbacks.get(decision, "Decision made based on my financial situation.")

# ─────────────────────────────────────────────
# AGGREGATION
# ─────────────────────────────────────────────

def aggregate(results, scenario):
    total = len(results)
    buy_r   = [r for r in results if r["decision"] == "Buy"]
    delay_r = [r for r in results if r["decision"] == "Delay"]
    switch_r= [r for r in results if r["decision"] == "Switch"]

    seg_map = {}
    for r in results:
        s = r["segment"]
        if s not in seg_map:
            seg_map[s] = {"Buy": 0, "Delay": 0, "Switch": 0, "total": 0}
        seg_map[s][r["decision"]] += 1
        seg_map[s]["total"] += 1

    from collections import Counter
    def top_reason(arr):
        if not arr: return None
        c = Counter(r["primary_reason_code"] for r in arr)
        top = c.most_common(1)[0]
        return {"code": top[0], "count": top[1]}

    avg = lambda k: round(sum(r[k] for r in results) / total, 3)

    return {
        "total": total,
        "adoption_rate":   round(len(buy_r)   / total, 3),
        "delay_rate":      round(len(delay_r)  / total, 3),
        "switch_rate":     round(len(switch_r) / total, 3),
        "revenue_forecast": len(buy_r) * scenario["price"],
        "revenue_at_risk":  (len(delay_r) + len(switch_r)) * scenario["price"],
        "confidence_weighted_adoption": round(sum(r["confidence"] for r in buy_r) / total, 3),
        "avg_affordability":   avg("affordability_score"),
        "avg_practicality":    avg("practicality_score"),
        "competitive_threat":  avg("competitor_attractiveness"),
        "avg_infra_dependency":avg("infrastructure_dependency_score"),
        "segment_adoption": {s: round(v["Buy"] / v["total"], 2) for s, v in seg_map.items()},
        "segment_breakdown": seg_map,
        "top_delay_reason":  top_reason(delay_r),
        "top_switch_reason": top_reason(switch_r),
        "top_buy_reason":    top_reason(buy_r),
        "individual_results": results,
    }

# ─────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────

@app.route("/api/simulate", methods=["POST"])
def simulate():
    """
    Main endpoint. Called by the HTML dashboard on every Run.
    Body: { scenario, n_personas, use_llm, seed }
    """
    body = request.json
    scenario = body.get("scenario", {})
    n = int(body.get("n_personas", 40))
    use_llm = bool(body.get("use_llm", False))
    seed = int(body.get("seed", 42))

    personas = generate_personas(n, seed)
    results = []

    for persona in personas:
        d = compute_decision(persona, scenario)
        d["persona_id"] = persona["persona_id"]
        d["segment"] = persona["segment"]
        d["age"] = persona["age"]
        d["monthly_income"] = persona["monthly_income"]

        # Only call LLM if explicitly requested (slow but richer)
        if use_llm:
            d["rationale"] = get_llm_rationale(persona, scenario, d["decision"])
        else:
            d["rationale"] = None

        results.append(d)

    summary = aggregate(results, scenario)
    return jsonify({"success": True, "data": summary})


@app.route("/api/ab_test", methods=["POST"])
def ab_test():
    """
    Run multiple scenarios at once and return comparison.
    Body: { scenarios: { label: scenario }, n_personas, seed }
    """
    body = request.json
    scenarios = body.get("scenarios", {})
    n = int(body.get("n_personas", 40))
    seed = int(body.get("seed", 42))

    personas = generate_personas(n, seed)  # Same personas for fair comparison

    results = {}
    for label, scenario in scenarios.items():
        persona_results = []
        for persona in personas:
            d = compute_decision(persona, scenario)
            d["persona_id"] = persona["persona_id"]
            d["segment"] = persona["segment"]
            d["age"] = persona["age"]
            d["monthly_income"] = persona["monthly_income"]
            persona_results.append(d)
        results[label] = aggregate(persona_results, scenario)

    # Cross-scenario comparison
    comparison = {
        label: {
            "adoption_rate": r["adoption_rate"],
            "revenue_forecast": r["revenue_forecast"],
            "revenue_at_risk": r["revenue_at_risk"],
            "competitive_threat": r["competitive_threat"],
        }
        for label, r in results.items()
    }

    best_revenue  = max(comparison, key=lambda k: comparison[k]["revenue_forecast"])
    best_adoption = max(comparison, key=lambda k: comparison[k]["adoption_rate"])

    return jsonify({
        "success": True,
        "results": results,
        "comparison": comparison,
        "recommendation": {
            "best_revenue_scenario": best_revenue,
            "best_adoption_scenario": best_adoption,
            "insight": f"'{best_revenue}' maximizes revenue. '{best_adoption}' captures widest market."
        }
    })


@app.route("/api/rationale", methods=["POST"])
def rationale():
    """
    Get LLM rationale for a single persona. Called on-demand from frontend.
    Body: { persona, scenario, decision }
    """
    body = request.json
    persona  = body["persona"]
    scenario = body["scenario"]
    decision = body["decision"]

    text = get_llm_rationale(persona, scenario, decision)
    return jsonify({"success": True, "rationale": text})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "MarketMind API is running"})


@app.route("/")
def serve_dashboard():
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    with open(path, encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}


if __name__ == "__main__":
    print("🚀 MarketMind running!")
    print("   ✅ Open → http://localhost:5000")
    print("   ✅ Flip the toggle to AI API mode in the dashboard")
    app.run(debug=True, port=5000)
