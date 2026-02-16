from langchain_core.tools import Tool
from langchain_community.tools import DuckDuckGoSearchRun

# Option 1: Use DuckDuckGo if internet is available and requested
# search = DuckDuckGoSearchRun()

# Option 2: Mocked/Simulated knowledge for stability in this demo
def query_medical_guidelines(query: str) -> str:
    """
    Simulates retrieval of medical guidelines.
    In a real app, this would query a vector DB or specific medical API.
    """
    # Simple hardcoded responses for demonstration
    query_lower = query.lower()
    if "pneumonia" in query_lower:
        return "Guideline: Community-acquired pneumonia diagnosis involves chest X-ray showing infiltrates and clinical symptoms like cough, fever, and dyspnea. First-line treatment for healthy outpatients includes amoxicillin or doxycycline."
    if "diabetes" in query_lower:
        return "Guideline: Diabetes diagnosis is based on A1C >= 6.5% or Fasting Plasma Glucose >= 126 mg/dL. Management includes lifestyle changes, metformin, and insulin if needed."
    if "hypertension" in query_lower:
        return "Guideline: Hypertension is defined as BP >= 130/80 mmHg. Initial treatment includes lifestyle modification and antihypertensive medication (ACE inhibitors, ARBs, etc.)."
    
    return f"No specific guideline found for '{query}'. General advice: Conduct thorough physical exam and history taking."

medical_knowledge_tool = Tool(
    name="MedicalGuidelines",
    func=query_medical_guidelines,
    description="Useful for retrieving medical guidelines and standard diagnostic criteria for various conditions."
)
