from typing import List, Any
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from src.core.llm import get_reasoning_llm
from src.tools.medical_knowledge import medical_knowledge_tool
from src.tools.visual_perception import visual_perception_tool

def create_diagnostician_agent():
    """
    Creates the Diagnostician Agent.
    This agent has access to tools and executes the plan.
    """
    llm = get_reasoning_llm()
    tools = [medical_knowledge_tool, visual_perception_tool]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Case-level Diagnostician Agent. Your task is to execute the diagnostic plan provided to you step-by-step. "
                   "You have access to medical knowledge and visual analysis tools. "
                   "Use them to gather evidence. "
                   "After gathering sufficient evidence, provide a Final Diagnosis with reasoning."),
        ("human", "Patient Case: {patient_case}\n\nDiagnostic Plan:\n{plan}\n\nExecute the plan and find the diagnosis."),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)
    
    return agent_executor

def run_diagnosis(patient_case: str, plan_steps: List[str]) -> str:
    """
    Runs the diagnostician agent with the given case and plan.
    """
    agent = create_diagnostician_agent()
    plan_str = "\n".join([f"{i+1}. {step}" for i, step in enumerate(plan_steps)])
    
    result = agent.invoke({
        "patient_case": patient_case,
        "plan": plan_str
    })
    
    return result["output"]
