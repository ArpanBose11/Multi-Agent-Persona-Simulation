from crewai import LLM

local_llm = LLM(
    model="ollama/llama3:8b",
    api_base="http://localhost:11434"
)