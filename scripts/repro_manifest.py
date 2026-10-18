"""Record exact published checkout, installed versions and actual JUnit outcomes."""
import argparse,json,platform,subprocess,sys,importlib.metadata,xml.etree.ElementTree as ET,hashlib
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--git',default='git');p.add_argument('--junit',nargs='+',required=True);p.add_argument('--output',default='data/audit/reproduction.json');a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    def git(*args):return subprocess.check_output([a.git,*args],cwd=root,text=True).strip()
    reports=[]
    for path in a.junit:
        node=ET.parse(path).getroot();suites=[node] if node.tag=='testsuite' else list(node.iter('testsuite'))
        reports.append({'file':str(path),'tests':sum(int(s.get('tests',0)) for s in suites),'failures':sum(int(s.get('failures',0)) for s in suites),'errors':sum(int(s.get('errors',0)) for s in suites),'skipped':sum(int(s.get('skipped',0)) for s in suites),'seconds':sum(float(s.get('time',0)) for s in suites)})
    hashes={str(f.relative_to(root)).replace('\\','/'):hashlib.sha256(f.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for f in sorted((root/'trusslab').glob('*.py'))}
    result={'commit':git('rev-parse','HEAD'),'tracked_changes':git('status','--porcelain','--untracked-files=no'),'remote':git('remote','get-url','origin'),'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'junit':reports,'source_sha256':hashes}
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'commit':result['commit'],'tracked_changes':result['tracked_changes'],'junit':reports},indent=2))
if __name__=='__main__':main()
