import streamlit as st
from simulation.persona_simulation import run_full_simulation, personas

st.set_page_config(page_title="Ola Market Simulation Lab", layout="wide")

st.title("🚀 Ola EV Market Simulation Lab")

st.sidebar.header("Scenario Inputs")

price = st.sidebar.number_input("Price (₹)", value=120000)
range_km = st.sidebar.number_input("Range (km)", value=120)
emi = st.sidebar.number_input("EMI (₹)", value=3000)
competitor_price = st.sidebar.number_input("Competitor Price (₹)", value=110000)

scenario = {
    "price": price,
    "range": range_km,
    "emi": emi,
    "competitor_price": competitor_price
}

if st.sidebar.button("Run Simulation"):

    with st.spinner("Simulating market behavior..."):
        metrics = run_full_simulation(personas, scenario)

    if "error" in metrics:
        st.error("Simulation failed.")
    else:
        st.subheader("📊 Executive Metrics")

        col1, col2, col3 = st.columns(3)

        col1.metric("Adoption Rate", f"{metrics['adoption_rate']*100:.1f}%")
        col2.metric("Revenue Forecast", f"₹{metrics['revenue_forecast']:,}")
        col3.metric("Revenue at Risk", f"₹{metrics['revenue_at_risk']:,}")
        st.write(f"⏱ Simulation Time: {metrics['generation_time_seconds']} seconds")

        st.subheader("🧠 Behavioral Insights")

        st.write("Top Buy Reason:", metrics["top_buy_reason"])
        st.write("Top Delay Reason:", metrics["top_delay_reason"])
        st.write("Top Switch Reason:", metrics["top_switch_reason"])

        st.subheader("📈 Price Sensitivity")

        elasticity_data = {
            "Highly Sensitive": metrics["highly_price_sensitive_pct"],
            "Neutral": metrics["neutral_price_sensitive_pct"],
            "Low Sensitive": metrics["low_price_sensitive_pct"],
        }

        st.bar_chart(elasticity_data)
        