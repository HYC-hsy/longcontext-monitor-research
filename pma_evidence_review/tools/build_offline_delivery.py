"""Build a synthetic-only engineering bundle. No model/profile imports or network."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import zipfile

from pma_evidence_review.focus_review import focus_plan, review
from pma_evidence_review.location import locate
from pma_evidence_review.tests.test_focus_review import changed, reply
from pma_evidence_review.transport import CapturedTransport, FakeClient


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    parser.add_argument('--code-sha',required=True)
    args=parser.parse_args()
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    def write(name,value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    p=changed('If PATH is exported, it runs. Task completed successfully. Only this session.\n\n'
              '- Keep the open question?\n```python\nvalue = 3.14\n```\n完成😀。')
    plan=focus_plan(p)
    requests=[x['request'] for x in plan['whole_plans'] if x['request']]
    requests += [f['request'] for x in plan['operations'] for f in x['focuses'] if f['request']]
    responses=[reply(op_index=r['op_index']) for r in requests]
    write('synthetic-input.json',p)
    write('synthetic-plan.json',plan)
    write('synthetic-responses.json',responses)
    transport=CapturedTransport(FakeClient(responses),out,fake=True)
    report=asyncio.run(review(p,transport,locator=locate))
    report['calls']={'client_calls':transport.calls,'fake':True,'network_calls':0,'provider_retries':0}
    write('synthetic-report.json',report)
    demo='\n'.join(json.dumps(x['focus'],ensure_ascii=False) for op in plan['operations'] for x in op['focuses'])
    (out/'verbatim-spans.jsonl').write_text(demo+'\n',encoding='utf-8')
    for name in ('FOCUS_HANDOFF.md','REUSE.md'):
        (out/name).write_bytes((root/name).read_bytes())
    logs=root/'test-records-focus'
    for path in sorted(logs.glob('*.txt')):
        (out/path.name).write_bytes(path.read_bytes())
    (out/'README.txt').write_text('ENGINEERING ACCEPTANCE ONLY: synthetic fake responses, no real model diagnosis.\n'
        'Whole baseline: 77f0f91dc4f508c9ef8e39c9f01e1d50c59eebd7.\n'
        'Reproduce from the code SHA in INDEX.json using FOCUS_HANDOFF.md.\n',encoding='utf-8')
    entries=[{'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(out.iterdir()) if p.is_file()]
    write('INDEX.json',{'kind':'offline-engineering-acceptance-not-model-diagnosis',
        'code_sha':args.code_sha,'files':entries,'contains_real_model_results':False})
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(out.iterdir()):
            info=zipfile.ZipInfo(path.name,date_time=(2026,10,26,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,path.read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for row in entries:
            data=z.read(row['path'])
            assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,
        'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))


if __name__=='__main__':
    main()
