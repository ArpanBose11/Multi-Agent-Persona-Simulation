import os
import json
import random
import time
from collections import Counter

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["LITELLM_TELEMETRY"] = "false"

# ─────────────────────────────────────────────
# SEGMENT-AWARE PERSONA GENERATION
# Each segment has realistic attribute distributions
# ─────────────────────────────────────────────

SEGMENT_PROFILES = {
    "Urban Commuter": {
        "age_range": (25, 40),
        "income_range": (40000, 90000),
        "price_sensitivity": (0.3, 0.5),
        "brand_trust": (0.5, 0.8),
        "range_anxiety": (0.2, 0.5),
        "charging_access": (0.5, 0.9),   # Lives in apartment, some access
        "risk_tolerance": (0.4, 0.7),
        "description": "City professional, daily commute < 40 km, has parking"
    },
    "Student": {
        "age_range": (18, 24),
        "income_range": (5000, 20000),
        "price_sensitivity": (0.7, 1.0),
        "brand_trust": (0.3, 0.6),
        "range_anxiety": (0.4, 0.7),
        "charging_access": (0.2, 0.5),   # Hostel/PG, limited access
        "risk_tolerance": (0.5, 0.9),
        "description": "College student, price-first, open to new tech"
    },
    "Gig Rider": {
        "age_range": (22, 35),
        "income_range": (15000, 35000),
        "price_sensitivity": (0.6, 0.9),
        "brand_trust": (0.3, 0.6),
        "range_anxiety": (0.6, 0.9),     # Range is livelihood
        "charging_access": (0.3, 0.6),
        "risk_tolerance": (0.3, 0.6),
        "description": "Delivery/ride-share driver, range = income security"
    },
    "Eco Conscious Buyer": {
        "age_range": (28, 50),
        "income_range": (50000, 120000),
        "price_sensitivity": (0.2, 0.5),
        "brand_trust": (0.6, 0.9),
        "range_anxiety": (0.1, 0.4),
        "charging_access": (0.6, 1.0),   # Owns home, likely has charger
        "risk_tolerance": (0.5, 0.8),
        "description": "Values sustainability, willing to pay premium"
    },
    "Price Sensitive Worker": {
        "age_range": (30, 50),
        "income_range": (10000, 30000),
        "price_sensitivity": (0.8, 1.0),
        "brand_trust": (0.2, 0.5),
        "range_anxiety": (0.5, 0.8),
        "charging_access": (0.1, 0.4),
        "risk_tolerance": (0.1, 0.4),
        "description": "Blue-collar worker, every rupee counts"
    },
    "Suburban Family": {
        "age_range": (32, 50),
        "income_range": (35000, 80000),
        "price_sensitivity": (0.4, 0.7),
        "brand_trust": (0.5, 0.8),
        "range_anxiety": (0.5, 0.8),     # Weekend trips matter
        "charging_access": (0.4, 0.7),
        "risk_tolerance": (0.2, 0.5),
        "description": "Family vehicle, safety & range paramount"
    },
    "Tech Early Adopter": {
        "age_range": (22, 38),
        "income_range": (60000, 150000),
        "price_sensitivity": (0.1, 0.4),
        "brand_trust": (0.4, 0.7),
        "range_anxiety": (0.1, 0.3),
        "charging_access": (0.6, 1.0),
        "risk_tolerance": (0.7, 1.0),
        "description": "Wants the latest tech, brand prestige matters less"
    },
    "Rural Buyer": {
        "age_range": (25, 55),
        "income_range": (8000, 25000),
        "price_sensitivity": (0.7, 1.0),
        "brand_trust": (0.4, 0.7),
        "range_anxiety": (0.7, 1.0),     # Charging infra is poor
        "charging_access": (0.0, 0.2),
        "risk_tolerance": (0.1, 0.3),
        "description": "Low infra access, high range anxiety, risk-averse"
    }
}


def rand_in(low, high, decimals=2):
    return round(random.uniform(low, high), decimals)


def generate_personas(n=30, seed=42):
    random.seed(seed)
    personas = []
    segments = list(SEGMENT_PROFILES.keys())

    for i in range(n):
        segment = segments[i % len(segments)]
        profile = SEGMENT_PROFILES[segment]

        age_lo, age_hi = profile["age_range"]
        inc_lo, inc_hi = profile["income_range"]

        persona = {
            "persona_id": i + 1,
            "segment": segment,
            "description": profile["description"],
            "age": random.randint(age_lo, age_hi),
            "monthly_income": random.randint(inc_lo // 1000, inc_hi // 1000) * 1000,
            "price_sensitivity": rand_in(*profile["price_sensitivity"]),
            "brand_trust": rand_in(*profile["brand_trust"]),
            "range_anxiety": rand_in(*profile["range_anxiety"]),
            "charging_access": rand_in(*profile["charging_access"]),
            "risk_tolerance": rand_in(*profile["risk_tolerance"]),
        }
        personas.append(persona)

    return personas


# ─────────────────────────────────────────────
# DETERMINISTIC DECISION ENGINE
# ─────────────────────────────────────────────

def compute_economic_scores(persona, scenario):
    annual_income = persona["monthly_income"] * 12
    price_ratio = scenario["price"] / annual_income
    affordability = max(0, min(1, 1 - price_ratio))

    emi_ratio = scenario["emi"] / persona["monthly_income"]
    emi_pressure = max(0, min(1, 1 - emi_ratio))

    price_gap = scenario["price"] - scenario["competitor_price"]
    competitor_threat = max(0, min(1, price_gap / scenario["competitor_price"])) if scenario["competitor_price"] else 1

    expected_min_range = 100
    practicality = max(0, min(1, scenario["range"] / (expected_min_range + persona["range_anxiety"] * 50)))

    return affordability, emi_pressure, competitor_threat, practicality


def compute_decision(persona, scenario):
    affordability, emi_pressure, competitor, practicality = compute_economic_scores(persona, scenario)

    brand_bias = persona["brand_trust"]
    infra_bias = 1 - persona["charging_access"]

    score = (
        affordability * 0.30 +
        emi_pressure * 0.15 +
        practicality * 0.20 +
        (1 - competitor) * 0.20 +
        brand_bias * 0.10 +
        persona["risk_tolerance"] * 0.05
    )

    # Price sensitivity pulls score down
    score *= (1 - persona["price_sensitivity"] * 0.3)

    if score >= 0.60:
        decision = "Buy"
    elif competitor >= 0.65:
        decision = "Switch"
    else:
        decision = "Delay"

    confidence = round(score, 3)

    factors = {
        "PRICE_SENSITIVE": round(1 - affordability, 3),
        "RANGE_ANXIETY": round(1 - practicality, 3),
        "COMPETITOR_THREAT": round(competitor, 3),
        "INFRA_DEPENDENT": round(infra_bias, 3),
        "EMI_STRESS": round(1 - emi_pressure, 3),
    }
    sorted_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)
    primary_reason = sorted_factors[0][0]
    secondary_reason = sorted_factors[1][0]

    return {
        "decision": decision,
        "confidence": confidence,
        "primary_reason_code": primary_reason,
        "secondary_reason_code": secondary_reason,
        "affordability_score": round(affordability, 3),
        "practicality_score": round(practicality, 3),
        "competitor_attractiveness": round(competitor, 3),
        "infrastructure_dependency_score": round(infra_bias, 3),
        "price_elasticity_signal": round(persona["price_sensitivity"] * -1 + 0.5, 3),
        "emi_pressure_score": round(1 - emi_pressure, 3),
    }


# ─────────────────────────────────────────────
# LLM QUALITATIVE RATIONALE (genuine contribution)
# ─────────────────────────────────────────────

def generate_qualitative_rationale(persona, scenario, decision_result):
    """
    Uses LLM only for what it's genuinely good at: human-like reasoning text.
    Decision logic stays deterministic for consistency.
    """
    try:
        from crewai import Task, Crew
        from agents.decision_agent import decision_agent

        prompt = f"""
You are a {persona['age']}-year-old {persona['segment']} in India with a monthly income of ₹{persona['monthly_income']:,}.

An EV is priced at ₹{scenario['price']:,} (EMI: ₹{scenario['emi']:,}/month). Range: {scenario['range']} km.
A competitor offers a similar EV at ₹{scenario['competitor_price']:,}.

The simulation predicts you will: {decision_result['decision']}

Write ONE sentence (max 20 words) explaining your decision in first person, as this persona.
Be specific to their life situation. Do not use generic language.
Return ONLY the sentence, nothing else.
"""
        task = Task(description=prompt, expected_output="One sentence rationale", agent=decision_agent)
        crew = Crew(agents=[decision_agent], tasks=[task])
        result = crew.kickoff()
        return str(result).strip().strip('"')
    except Exception:
        # Fallback rationale if LLM fails
        d = decision_result['decision']
        segment = persona['segment']
        if d == "Buy":
            return f"As a {segment}, the EV fits my commute needs and budget."
        elif d == "Switch":
            return f"The competitor offers better value for my {segment} lifestyle."
        else:
            return f"I'll wait until charging infrastructure improves in my area."


# ─────────────────────────────────────────────
# AGGREGATION
# ─────────────────────────────────────────────

def aggregate_results(results, scenario):
    price = scenario["price"]
    total = len(results)
    if total == 0:
        return {}

    buy_r = [r for r in results if r["decision"] == "Buy"]
    delay_r = [r for r in results if r["decision"] == "Delay"]
    switch_r = [r for r in results if r["decision"] == "Switch"]

    adoption_rate = len(buy_r) / total
    delay_rate = len(delay_r) / total
    switch_rate = len(switch_r) / total

    confidence_weighted_adoption = sum(r["confidence"] for r in buy_r) / total if total else 0

    revenue_forecast = len(buy_r) * price
    revenue_at_risk = (len(delay_r) + len(switch_r)) * price

    # Segment breakdown
    segment_breakdown = {}
    for r in results:
        seg = r.get("segment", "Unknown")
        if seg not in segment_breakdown:
            segment_breakdown[seg] = {"Buy": 0, "Delay": 0, "Switch": 0, "total": 0}
        segment_breakdown[seg][r["decision"]] += 1
        segment_breakdown[seg]["total"] += 1

    segment_adoption = {
        seg: round(v["Buy"] / v["total"], 2)
        for seg, v in segment_breakdown.items()
    }

    avg = lambda key: round(sum(r[key] for r in results) / total, 3)

    top_buy_reason = Counter(r["primary_reason_code"] for r in buy_r).most_common(1)
    top_delay_reason = Counter(r["primary_reason_code"] for r in delay_r).most_common(1)
    top_switch_reason = Counter(r["primary_reason_code"] for r in switch_r).most_common(1)

    return {
        "scenario": scenario,
        "total_personas": total,
        "adoption_rate": round(adoption_rate, 3),
        "delay_rate": round(delay_rate, 3),
        "switch_rate": round(switch_rate, 3),
        "confidence_weighted_adoption": round(confidence_weighted_adoption, 3),
        "revenue_forecast": revenue_forecast,
        "revenue_at_risk": revenue_at_risk,
        "avg_affordability": avg("affordability_score"),
        "avg_practicality": avg("practicality_score"),
        "competitive_threat_index": avg("competitor_attractiveness"),
        "avg_price_elasticity": avg("price_elasticity_signal"),
        "avg_infrastructure_dependency": avg("infrastructure_dependency_score"),
        "segment_adoption_rates": segment_adoption,
        "segment_breakdown": segment_breakdown,
        "top_buy_reason": top_buy_reason[0][0] if top_buy_reason else None,
        "top_delay_reason": top_delay_reason[0][0] if top_delay_reason else None,
        "top_switch_reason": top_switch_reason[0][0] if top_switch_reason else None,
        "individual_results": results,
    }


# ─────────────────────────────────────────────
# MULTI-SCENARIO A/B TESTING (THE KEY FEATURE)
# ─────────────────────────────────────────────

def run_scenario(personas, scenario, use_llm_rationale=False):
    results = []
    for persona in personas:
        decision_result = compute_decision(persona, scenario)
        decision_result["persona_id"] = persona["persona_id"]
        decision_result["segment"] = persona["segment"]
        decision_result["age"] = persona["age"]
        decision_result["monthly_income"] = persona["monthly_income"]

        if use_llm_rationale:
            decision_result["rationale"] = generate_qualitative_rationale(persona, scenario, decision_result)

        results.append(decision_result)

    return aggregate_results(results, scenario)


def run_ab_test(personas, scenarios, use_llm_rationale=False):
    """
    Run multiple scenarios against the same persona universe.
    This is the core differentiator — instant A/B testing.
    """
    start = time.time()
    ab_results = {}

    for label, scenario in scenarios.items():
        print(f"  Running scenario: {label}...")
        ab_results[label] = run_scenario(personas, scenario, use_llm_rationale)

    elapsed = round(time.time() - start, 2)

    # Cross-scenario comparison
    comparison = {}
    for label, result in ab_results.items():
        comparison[label] = {
            "adoption_rate": result["adoption_rate"],
            "revenue_forecast": result["revenue_forecast"],
            "revenue_at_risk": result["revenue_at_risk"],
            "competitive_threat_index": result["competitive_threat_index"],
            "confidence_weighted_adoption": result["confidence_weighted_adoption"],
        }

    best_adoption = max(comparison, key=lambda k: comparison[k]["adoption_rate"])
    best_revenue = max(comparison, key=lambda k: comparison[k]["revenue_forecast"])

    return {
        "scenarios_tested": list(scenarios.keys()),
        "results": ab_results,
        "comparison": comparison,
        "recommendation": {
            "best_adoption_scenario": best_adoption,
            "best_revenue_scenario": best_revenue,
            "insight": f"'{best_revenue}' maximizes revenue. '{best_adoption}' maximizes market penetration."
        },
        "simulation_time_seconds": elapsed,
        "total_personas": len(personas),
    }


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    personas = generate_personas(n=40)

    # A/B test: 4 pricing scenarios
    scenarios = {
        "Aggressive Pricing (₹99K)": {
            "price": 99000, "range": 120, "emi": 2500, "competitor_price": 110000
        },
        "Current Pricing (₹1.2L)": {
            "price": 120000, "range": 120, "emi": 3000, "competitor_price": 110000
        },
        "Premium Pricing (₹1.4L)": {
            "price": 140000, "range": 150, "emi": 3500, "competitor_price": 110000
        },
        "Extended Range (₹1.3L, 180km)": {
            "price": 130000, "range": 180, "emi": 3200, "competitor_price": 110000
        },
    }

    print("\n🔬 Running Market Simulation A/B Test...")
    print(f"   Personas: {len(personas)} | Scenarios: {len(scenarios)}")
    print("=" * 60)

    ab_output = run_ab_test(personas, scenarios, use_llm_rationale=False)

    print("\n📊 COMPARISON RESULTS:")
    print("-" * 60)
    for scenario_name, metrics in ab_output["comparison"].items():
        print(f"\n  {scenario_name}")
        print(f"    Adoption Rate:     {metrics['adoption_rate']*100:.1f}%")
        print(f"    Revenue Forecast:  ₹{metrics['revenue_forecast']:,}")
        print(f"    Revenue at Risk:   ₹{metrics['revenue_at_risk']:,}")
        print(f"    Competitive Threat: {metrics['competitive_threat_index']:.2f}")

    rec = ab_output["recommendation"]
    print(f"\n💡 RECOMMENDATION:")
    print(f"   {rec['insight']}")
    print(f"\n⏱  Simulation completed in {ab_output['simulation_time_seconds']}s")

    # Save full output for dashboard
    with open("simulation_output.json", "w") as f:
        output_copy = {k: v for k, v in ab_output.items() if k != "results"}
        for label, result in ab_output["results"].items():
            result_copy = {k: v for k, v in result.items() if k != "individual_results"}
            output_copy.setdefault("detailed_results", {})[label] = result_copy
        json.dump(output_copy, f, indent=2)
    print("\n✅ Full output saved to simulation_output.json")
