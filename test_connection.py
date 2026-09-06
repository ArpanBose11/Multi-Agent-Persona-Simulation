from crewai import Agent, Task, Crew, LLM

# Use CrewAI's built-in LLM config for Ollama
llm = LLM(
    model="ollama/llama3:8b",
    base_url="http://localhost:11434"
)

agent = Agent(
    role="Test Agent",
    goal="Respond briefly",
    backstory="You are testing connectivity to Ollama.",
    llm=llm,
    verbose=True
)

task = Task(
    description="Say hello in one sentence.",
    expected_output="A single short greeting sentence.",
    agent=agent
)

crew = Crew(
    agents=[agent],
    tasks=[task],
    verbose=True
)

result = crew.kickoff()
print(result)