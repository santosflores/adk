from google.adk import Agent

AGENT_MODEL = "gemini-3.1-flash-lite"

root_agent = Agent(
    name="root_agent",
    model=AGENT_MODEL,
)