"""Source/dependency inventory, intentionally excludes installed dependencies."""
import ast,hashlib,json,sys,platform,importlib.metadata
from pathlib import Path
root=Path(__file__).resolve().parents[1]
rows=[];references=[]
for p in sorted(root.rglob('*.py')):
    if any(x in p.relative_to(root).parts for x in ('.venv','venv','.git','__pycache__','data','build','dist')):continue
    text=p.read_text(encoding='utf-8-sig');tree=ast.parse(text)
    imports=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.ImportFrom):imports.append('.'*n.level+(n.module or ''))
        elif isinstance(n,ast.Import):imports.extend(a.name for a in n.names)
    rows.append({'path':p.relative_to(root).as_posix(),'lines':len(text.splitlines()),'sha256':hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'imports':sorted(set(imports)),'definitions':[n.name for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))]})
    for i,line in enumerate(text.splitlines(),1):
        if any(term in line.lower() for term in ('case_i','caso i','5060.','6 nodos','10 barras','range(10)','full(10')):
            references.append({'file':p.relative_to(root).as_posix(),'line':i,'text':line.strip()})
result={'python':sys.version,'platform':platform.platform(),'sources':rows,'benchmark_references':references,'installed_packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'scope':'AST of all project Python and tests; installed, generated, data directories excluded'}
out=root/'data/audit/source_map.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(out,len(rows),'Python files')
