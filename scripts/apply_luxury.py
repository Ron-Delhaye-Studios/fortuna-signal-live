"""Idempotently link the public luxury layer after a static-site export.
Run with --check in CI. Private dashboard and head-only redirects are excluded.
No private generator, credentials, editorial content, or engine settings needed.
"""
import argparse
from pathlib import Path
import os,re

ROOT = Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    missing=[]
    for page in sorted(ROOT.rglob('*.html')):
        relative=page.relative_to(ROOT)
        if relative.parts[0] in {'dashboard','.git'}:
            continue
        text=page.read_text()
        if not re.search(r'<body\b',text,re.I) or not re.search(r'</head>',text,re.I):
            continue
        href=os.path.relpath(ROOT/'assets/css/luxury.css',page.parent).replace(os.sep,'/')
        tag=f'<link rel="stylesheet" href="{href}" data-fortuna-luxury="1">'
        if tag in text:
            continue
        missing.append(str(relative))
        if not args.check:
            page.write_text(re.sub(r'</head>',tag+'\n</head>',text,count=1,flags=re.I))
    if args.check and missing:
        raise SystemExit('Missing luxury layer; run scripts/apply_luxury.py: '+', '.join(missing))
    print(('Checked' if args.check else 'Linked')+f' public luxury layer: {len(missing)} '+('missing' if args.check else 'updated'))
if __name__=='__main__':
    main()
