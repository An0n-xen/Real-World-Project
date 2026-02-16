from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from src.core.llm import get_reasoning_llm

class DiagnosticPlan(BaseModel):
    steps: List[str] = Field(description="A sequential list of diagnostic steps to follow.")
    reasoning: str = Field(description="Brief reasoning for the proposed plan.")

def create_planner_agent():
    """
    Creates the Planner Agent chain.
    """
    llm = get_reasoning_llm()
    
    parser = PydanticOutputParser(pydantic_object=DiagnosticPlan)
    
    template = """You are a Task-level Planner Agent for a medical diagnosis system (MedAgent-Pro).
Your goal is to create a comprehensive, evidence-based diagnostic plan for a patient based on their initial case description.

The plan should outline the necessary steps to reach a confirmed diagnosis, including:
1. Analyzing key symptoms.
2. Checking relevant medical guidelines.
3. Requests for specific visual analysis if medical images are mentioned.
4. Synthesizing findings.

Patient Case:
{patient_case}

{format_instructions}

Provide the plan now.
"""
    
    prompt = ChatPromptTemplate.from_template(template)
    
    chain = prompt | llm | parser
    return chain

def generate_plan(patient_case: str) -> DiagnosticPlan:
    planner = create_planner_agent()
    parser = PydanticOutputParser(pydantic_object=DiagnosticPlan)
    output = planner.invoke({
        "patient_case": patient_case, 
        "format_instructions": parser.get_format_instructions()
    })
    return output
