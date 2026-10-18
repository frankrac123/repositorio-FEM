"""Engineering contracts shared by document, commands and solvers."""
from dataclasses import dataclass,asdict
from typing import TypedDict

@dataclass
class BoundaryCondition:
    node_id: int
    restrained: list[bool]
    coordinate_system: str = 'Global'
    def validate(self):
        if self.coordinate_system!='Global' or len(self.restrained)!=3 or not all(isinstance(v,bool) for v in self.restrained):
            raise ValueError('Los apoyos requieren tres restricciones booleanas en ejes globales.')

class AnalysisResult(TypedDict,total=False):
    model_id: str
    model_fingerprint: str
    engine: str
    analysis_case: str
    analysis_status: str
    members: list[dict]
    displacements: dict[str,list[float]]
    reactions: dict[str,list[float]]
    validation: dict
    feasible: bool
    case_results: dict

@dataclass
class OptimizationProblem:
    objective: str
    variables: list[list[int]]
    lower: list[float]
    upper: list[float]
    stress_limit_ksi: float
    displacement_limit_in: float
    load_cases: list[str]
    def to_dict(self):return asdict(self)
