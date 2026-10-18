from pathlib import Path
import argparse
import json
from .core import benchmark, save_project, load_project
from .fem import solve


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['diagnose','fem','sap','optimize'])
    p.add_argument('--project')
    p.add_argument('--output', default='data')
    p.add_argument('--method', choices=['SLSQP','DE'], default='SLSQP')
    args = p.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    m = load_project(args.project)[0] if args.project else benchmark()
    if args.command == 'diagnose':
        from .sap import diagnose
        r = diagnose()
        (out/'diagnostic.json').write_text(json.dumps(r, indent=2), encoding='utf-8')
    elif args.command == 'fem':
        r = solve(m)
        save_project(out/'case_i.trusslab.json', m, r)
    elif args.command == 'sap':
        from .sap import analyze
        r = analyze(m, out, progress=print)
        save_project(out/'sap_case_i.trusslab.json', m, r)
    else:
        from .optimization import optimize
        m, r, h = optimize(m, method=args.method)
        save_project(out/'optimized.trusslab.json', m, r, h)
    print(json.dumps(r, indent=2, ensure_ascii=True))


if __name__ == '__main__':
    main()
