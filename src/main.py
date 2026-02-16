import sys
from src.agents.planner import generate_plan
from src.agents.diagnostician import run_diagnosis
from src.core.utils import print_separator

def main():
    print_separator()
    print("MedAgent-Pro: Evidence-based Multi-modal Medical Diagnosis System")
    print_separator()

    # 1. Get Patient Case
    if len(sys.argv) > 1:
        patient_case = " ".join(sys.argv[1:])
    else:
        print("No case provided. Using default demo case.")
        patient_case = (
            "45-year-old male presenting with persistent cough for 2 weeks, "
            "fever of 38.5C, and shortness of breath. "
            "History of smoking. "
            "Chest X-ray image available at 'demo_xray.jpg' shows lower lobe consolidation."
        )
    
    print(f"Patient Case: {patient_case}")
    print_separator()

    # 2. Planner Agent
    print("Step 1: Planner Agent - Generating Diagnostic Plan...")
    try:
        plan_output = generate_plan(patient_case)
        print("\nDiagnostic Plan Generated:")
        for i, step in enumerate(plan_output.steps):
            print(f"{i+1}. {step}")
        print(f"\nReasoning: {plan_output.reasoning}")
    except Exception as e:
        print(f"Error generating plan: {e}")
        return

    print_separator()

    # 3. Diagnostician Agent
    print("Step 2: Diagnostician Agent - Executing Plan...")
    try:
        diagnosis = run_diagnosis(patient_case, plan_output.steps)
        print("\nFinal Diagnosis & Report:")
        print(diagnosis)
    except Exception as e:
        print(f"Error during diagnosis execution: {e}")

    print_separator()

if __name__ == "__main__":
    main()
