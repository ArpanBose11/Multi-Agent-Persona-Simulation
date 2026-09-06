from crewai import Agent, LLM

# Explicit Ollama configuration for CrewAI 1.9.3
local_llm = LLM(
    model="ollama/llama3:8b",
    api_base="http://localhost:11434",
    temperature=0,
    top_p=1,
    top_k=0
)

decision_agent = Agent(
    role="EV Purchase Behavior Simulator",
    goal="Simulate realistic Indian EV purchase decisions.",
    backstory=(
        "You simulate Indian EV customers evaluating affordability, "
        "range, competitor pricing, and behavioral traits before making "
        "a structured decision."
    ),
    llm=local_llm,
    verbose=False
)