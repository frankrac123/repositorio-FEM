"""Public FEM interface. Units: kip, inch, ksi; weight: lb."""
from .engineering_types import AnalysisResult
from .truss_kernel import TrussKernel

def solve(model,case=None) -> AnalysisResult:
    case=case or model.active_case
    model.validate(case=case)
    result=TrussKernel(model).solve_case([b.area for b in model.members],case)
    result.update(engine='FEM · NumPy',model_id=model.project_id,model_fingerprint=model.fingerprint())
    return result

def compare(model,reference,candidate):
    from .validation import detailed_compare
    return detailed_compare(model,reference,candidate)
