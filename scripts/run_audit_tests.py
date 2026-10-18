"""Run pytest with direct file handles; visible SAP copies may remain open.

PowerShell native redirection can wait for pipe EOF inherited by GUI children.
The supervisor waits for pytest's process handle, not for a SAP window to close.
"""
import argparse,json,subprocess,sys,time
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='data/audit/test_process');p.add_argument('pytest_args',nargs=argparse.REMAINDER);a=p.parse_args()
    args=a.pytest_args
    if args[:1]==['--']:args=args[1:]
    args=args or ['-q']
    prefix=Path(a.output);prefix.parent.mkdir(parents=True,exist_ok=True)
    log=prefix.with_suffix('.txt');started=time.perf_counter()
    with log.open('w',encoding='utf-8') as stream:
        completed=subprocess.run([sys.executable,'-m','pytest',*args],stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,close_fds=True)
    text=log.read_text(encoding='utf-8',errors='replace')
    summary={'command':[sys.executable,'-m','pytest',*args],'return_code':completed.returncode,'elapsed_seconds':time.perf_counter()-started,'log':str(log.resolve()),'native_rpc_diagnostics':text.count('Windows fatal exception: code 0x800706ba')}
    prefix.with_suffix('.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('\n'.join(text.splitlines()[-4:]));print(json.dumps(summary,indent=2))
    return completed.returncode
if __name__=='__main__':raise SystemExit(main())
