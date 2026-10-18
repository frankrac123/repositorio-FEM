"""Small independent engineering examples, also used for integration regressions."""
from .core import Model,Node,Member,Material,Section,LoadPattern,AnalysisCase

def triangle():
    m=Model.empty('2D',name='Triángulo 2D · materiales y cargas')
    m.nodes=[Node(1,[0.,0.,0.],[True,False,True]),Node(2,[120.,0.,0.],[False,False,True]),Node(3,[60.,0.,80.])]
    m.materials.append(Material('M2','Material E 10,000 ksi',10000.,.1))
    m.members=[Member(1,1,2,1.5,'M1','S1','base'),Member(2,1,3,2.,'M2',None,'diagonales'),Member(3,2,3,2.,'M1',None,'diagonales')]
    m.load_patterns=[LoadPattern('LC1','Vertical y peso propio','Dead',{'3':[0.,0.,-10.]},1.),LoadPattern('LC2','Horizontal','Wind',{'3':[4.,0.,-2.]})]
    m.analysis_cases=[AnalysisCase('C1','Vertical',{'LC1':1.}),AnalysisCase('C2','Horizontal',{'LC2':1.}),AnalysisCase('ULS','Combinación 1.2D + 1.6W',{'LC1':1.2,'LC2':1.6})]
    m.active_case='C1';return m

def spatial():
    m=Model.empty('3D',name='Trípode espacial · materiales y cargas')
    m.nodes=[Node(1,[0.,0.,0.],[True]*3),Node(2,[120.,0.,0.],[True]*3),Node(3,[0.,120.,0.],[True]*3),Node(4,[30.,40.,100.])]
    m.materials.extend([Material('M2','Material E 20,000 ksi',20000.,.2),Material('M3','Material E 10,000 ksi',10000.,.1)])
    m.members=[Member(1,1,4,3.,'M1'),Member(2,2,4,4.,'M2'),Member(3,3,4,5.,'M3')]
    m.load_patterns=[LoadPattern('LC1','Vertical y lateral','Other',{'4':[5.,-3.,-15.]}),LoadPattern('LC2','Otra dirección','Wind',{'4':[-6.,4.,-2.]})]
    m.analysis_cases=[AnalysisCase('C1','Caso 1',{'LC1':1.}),AnalysisCase('C2','Caso 2',{'LC2':1.}),AnalysisCase('ULS','Combinación',{'LC1':1.2,'LC2':1.6})]
    m.active_case='C1';return m
