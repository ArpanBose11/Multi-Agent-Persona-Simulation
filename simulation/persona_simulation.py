import os
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["LITELLM_TELEMETRY"] = "false"
from crewai import Task, Crew
from agents.decision_agent import decision_agent
import json
from collections import Counter
import time

def generate_personas(n=20):
    personas = []

    segments = [
        "Urban Commuter",
        "Student",
        "Gig Rider",
        "Eco Conscious Buyer",
        "Price Sensitive Worker"
    ]

    for i in range(n):
        segment = segments[i % len(segments)]

        persona = {
            "persona_id": i + 1,
            "segment": segment,
            "age": 20 + (i % 25),
            "monthly_income": 15000 + (i % 10) * 5000,
            "price_sensitivity": round((i % 10) / 10, 2),
            "brand_trust": round(((i + 3) % 10) / 10, 2),
            "range_anxiety": round(((i + 5) % 10) / 10, 2),
            "charging_access": round(((i + 7) % 10) / 10, 2),
            "risk_tolerance": round(((i + 2) % 10) / 10, 2)
        }

        personas.append(persona)

    return personas

personas = generate_personas()

scenario = {
    "price": 120000,
    "range": 120,
    "emi": 3000,
    "competitor_price": 110000
}

def build_prompt(persona, scenario):
    return f"""
You are simulating a realistic Indian EV buyer.

Persona Attributes:
- Age: {persona['age']}
- Monthly Income: {persona['monthly_income']}
- Price Sensitivity (0-1): {persona['price_sensitivity']}
- Brand Trust (0-1): {persona['brand_trust']}
- Range Anxiety (0-1): {persona['range_anxiety']}
- Charging Access (0-1): {persona['charging_access']}
- Risk Tolerance (0-1): {persona['risk_tolerance']}

EV Scenario:
- Price: {scenario['price']}
- Range (km): {scenario['range']}
- EMI: {scenario['emi']}
- Competitor Price: {scenario['competitor_price']}

Evaluate sequentially:
1. Affordability relative to income
2. Practical usability (range + charging)
3. Competitor comparison
4. Sensitivity to small price change (+5%)
5. Infrastructure dependence

Return ONLY valid JSON in EXACT format:

{{
  "affordability_score": 0.0,
  "practicality_score": 0.0,
  "competitor_attractiveness": 0.0,
  "price_elasticity_signal": 0.0,
  "infrastructure_dependency_score": 0.0
}}

All numeric values must be between 0 and 1 except price_elasticity_signal which ranges from -1 to 1.
Do not return explanations outside JSON.
"""
def build_batch_prompt(batch_personas, scenario):
    persona_block = ""

    for p in batch_personas:
        persona_block += f"""
Persona ID: {p['persona_id']}
Age: {p['age']}
Monthly Income: {p['monthly_income']}
Price Sensitivity: {p['price_sensitivity']}
Brand Trust: {p['brand_trust']}
Range Anxiety: {p['range_anxiety']}
Charging Access: {p['charging_access']}
Risk Tolerance: {p['risk_tolerance']}
---
"""

    return f"""
You are simulating multiple Indian EV buyers.

EV Scenario:
- Price: {scenario['price']}
- Range (km): {scenario['range']}
- EMI: {scenario['emi']}
- Competitor Price: {scenario['competitor_price']}

Below are multiple personas.

{persona_block}

For EACH persona return ONLY valid JSON.

Return a JSON ARRAY like:

[
  {{
    "persona_id": 1,
    "affordability_score": 0.0,
    "practicality_score": 0.0,
    "competitor_attractiveness": 0.0,
    "price_elasticity_signal": 0.0,
    "infrastructure_dependency_score": 0.0
  }}
]

Do not include explanations.
Only return a valid JSON array.
"""

def run_simulation(persona, scenario):
    prompt = build_prompt(persona, scenario)

    task = Task(
    description=prompt,
    expected_output="Structured JSON decision output",
    agent=decision_agent
)

    crew = Crew(
        agents=[decision_agent],
        tasks=[task]
    )

    result = crew.kickoff()

    return result

def run_batch_simulation(batch_personas, scenario):
    prompt = build_batch_prompt(batch_personas, scenario)

    task = Task(
        description=prompt,
        expected_output="JSON array of persona scores",
        agent=decision_agent
    )

    crew = Crew(
        agents=[decision_agent],
        tasks=[task]
    )

    result = crew.kickoff()

    return result

def extract_json(text):
    try:
        json_str = text.strip()

        if json_str.startswith("["):
            return json.loads(json_str)
        elif json_str.startswith("{"):
            return json.loads(json_str)
        else:
            start = json_str.find("[")
            end = json_str.rfind("]") + 1
            return json.loads(json_str[start:end])
    except:
        return {"error": "Invalid JSON", "raw_output": text}

def compute_economic_scores(persona, scenario):

    # 🔹 Income-based affordability
    annual_income = persona["monthly_income"] * 12
    price_ratio = scenario["price"] / annual_income

    affordability = max(0, min(1, 1 - price_ratio))

    # 🔹 EMI pressure
    emi_ratio = scenario["emi"] / persona["monthly_income"]
    emi_pressure = max(0, min(1, 1 - emi_ratio))

    # 🔹 Competitor threat
    price_gap = scenario["price"] - scenario["competitor_price"]

    if scenario["competitor_price"] == 0:
        competitor_threat = 1
    else:
        competitor_threat = max(0, min(1, (price_gap / scenario["competitor_price"])))

    # 🔹 Range practicality
    expected_min_range = 100
    practicality = max(0, min(1, scenario["range"] / (expected_min_range + persona["range_anxiety"] * 50)))

    return affordability, emi_pressure, competitor_threat, practicality

def compute_decision(persona, scenario):

    affordability, emi_pressure, competitor, practicality = compute_economic_scores(persona, scenario)

    # 🔹 Behavioral modifiers
    risk_bias = persona["risk_tolerance"]
    brand_bias = persona["brand_trust"]
    infra_bias = 1 - persona["charging_access"]

    # 🔹 Weighted market score
    score = (
        affordability * 0.35 +
        emi_pressure * 0.15 +
        practicality * 0.2 +
        (1 - competitor) * 0.2 +
        brand_bias * 0.1
    )

    # 🔹 Decision Logic
    if score >= 0.65:
        decision = "Buy"
    elif competitor >= 0.7:
        decision = "Switch"
    else:
        decision = "Delay"

    confidence = round(score, 2)

    # 🔹 Reason Attribution (deterministic)
    factors = {
        "PRICE_SENSITIVE": 1 - affordability,
        "RANGE_ANXIETY": 1 - practicality,
        "COMPETITOR_THREAT": competitor,
        "INFRA_DEPENDENT": infra_bias
    }

    sorted_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)

    primary_reason = sorted_factors[0][0]
    secondary_reason = sorted_factors[1][0]

    return decision, confidence, primary_reason, secondary_reason, affordability, practicality, competitor

def aggregate_results(results, price):
    total = len(results)

    buy_results = [r for r in results if r["decision"] == "Buy"]
    delay_results = [r for r in results if r["decision"] == "Delay"]
    switch_results = [r for r in results if r["decision"] == "Switch"]

    buy = len(buy_results)
    delay = len(delay_results)
    switch = len(switch_results)

    # Basic Rates
    adoption_rate = buy / total if total else 0
    delay_rate = delay / total if total else 0
    switch_rate = switch / total if total else 0

    # Confidence Weighted Adoption
    confidence_weighted_adoption = (
        sum(r["confidence"] for r in buy_results) / total if total else 0
    )

    # Revenue
    revenue_forecast = buy * price
    revenue_at_risk = (delay + switch) * price

    # Behavioral Averages
    avg_affordability = sum(float(r["affordability_score"]) for r in results) / total
    avg_practicality = sum(float(r["practicality_score"]) for r in results) / total
    avg_competitor = sum(float(r["competitor_attractiveness"]) for r in results) / total
    avg_elasticity = sum(float(r["price_elasticity_signal"]) for r in results) / total
    avg_infra_dependency = sum(float(r["infrastructure_dependency_score"]) for r in results) / total

    # Elasticity Segmentation
    highly_sensitive = sum(1 for r in results if r["price_elasticity_signal"] < -0.6) / total
    neutral = sum(1 for r in results if -0.3 <= r["price_elasticity_signal"] <= 0.3) / total
    low_sensitive = sum(1 for r in results if r["price_elasticity_signal"] > 0.3) / total

    # Top Reasons
    buy_reasons = Counter(r["primary_reason_code"] for r in buy_results)
    delay_reasons = Counter(r["primary_reason_code"] for r in delay_results)
    switch_reasons = Counter(r["primary_reason_code"] for r in switch_results)

    top_buy_reason = buy_reasons.most_common(1)[0][0] if buy_reasons else None
    top_delay_reason = delay_reasons.most_common(1)[0][0] if delay_reasons else None
    top_switch_reason = switch_reasons.most_common(1)[0][0] if switch_reasons else None

    return {
        "total_personas": total,

        "adoption_rate": adoption_rate,
        "delay_rate": delay_rate,
        "switch_rate": switch_rate,
        "confidence_weighted_adoption": confidence_weighted_adoption,

        "revenue_forecast": revenue_forecast,
        "revenue_at_risk": revenue_at_risk,

        "avg_affordability": avg_affordability,
        "avg_practicality": avg_practicality,
        "competitive_threat_index": avg_competitor,
        "avg_price_elasticity": avg_elasticity,
        "avg_infrastructure_dependency": avg_infra_dependency,

        "highly_price_sensitive_pct": highly_sensitive,
        "neutral_price_sensitive_pct": neutral,
        "low_price_sensitive_pct": low_sensitive,

        "top_buy_reason": top_buy_reason,
        "top_delay_reason": top_delay_reason,
        "top_switch_reason": top_switch_reason
    }

def run_full_simulation(personas, scenario):
    start_time = time.time()

    results = []
    batch_size = 10

    for i in range(0, len(personas), batch_size):

        batch = personas[i:i + batch_size]

        raw_output = run_batch_simulation(batch, scenario)
        parsed_batch = extract_json(str(raw_output))
        print("\n=== RAW BATCH OUTPUT ===")
        print(raw_output)
        print("\n==============================")
        print("RAW OUTPUT:")
        print(raw_output)
        print("------------------------------")
        print("PARSED:")
        print(parsed_batch)
        print("==============================")

        print("\n=== PARSED BATCH ===")
        print(parsed_batch)
        print("RAW BATCH OUTPUT:", raw_output)
        print("PARSED BATCH:", parsed_batch)

        if isinstance(parsed_batch, list):

            for parsed_output, persona in zip(parsed_batch, batch):

                decision, confidence, primary_reason, secondary_reason, affordability, practicality, competitor = compute_decision(persona, scenario)

                parsed_output["decision"] = decision
                parsed_output["confidence"] = confidence
                parsed_output["primary_reason_code"] = primary_reason
                parsed_output["secondary_reason_code"] = secondary_reason
                parsed_output["affordability_score"] = affordability
                parsed_output["practicality_score"] = practicality
                parsed_output["competitor_attractiveness"] = competitor
                parsed_output["infrastructure_dependency_score"] = 1 - persona["charging_access"]
                parsed_output["price_elasticity_signal"] = persona["price_sensitivity"]

                results.append(parsed_output)

    end_time = time.time()
    total_time = round(end_time - start_time, 2)

    if len(results) == 0:
        return {"error": "No valid results"}

    metrics = aggregate_results(results, scenario["price"])
    metrics["generation_time_seconds"] = total_time

    return metrics

if __name__ == "__main__":

    metrics = run_full_simulation(personas, scenario)

    print("\n--- METRICS ---")
    print(metrics)