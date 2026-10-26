"""Synthetic closed-citation acceptance package; never call a real model/profile."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import zipfile

from pma_evidence_review import citation_inputs as ci, citation_review as cr
from pma_evidence_review.tests.test_citation_review import synthetic,response
from pma_evidence_review.transport import CapturedTransport,FakeClient


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    parser.add_argument('--code-sha',required=True)
    args=parser.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    def write(name,value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    packet=synthetic()
    write('synthetic-citation-input.json',packet)
    plans=cr.requests(packet);write('synthetic-request-plan.json',plans)
    write('model-projection.json',cr.projection(packet,packet['operations'][0]))
    write('synthetic-responses.json',[response()])
    transport=CapturedTransport(FakeClient([response()]),out,fake=True)
    write('synthetic-report.json',asyncio.run(cr.review(packet,transport)))
    summaries=[]
    for sample in ('sqlite','html'):
        p=ci.build(root.parent,sample)
        summaries.append({'sample':sample,'citation_input_sha256':p['citation_input_sha256'],
            'parent_input_sha256':p['parent_input_sha256'],'operations':[
                {'op_index':r['operation']['op_index'],'action':r['operation']['action'],
                 'status':r['preparation']['status'],'issues':r['preparation']['issues']}
                for r in p['operations']]})
    write('public-sample-preparation-summary.json',summaries)
    for path in [root/'CITATION_HANDOFF.md',root/'REUSE.md',*sorted((root/'test-records-citation').glob('*.txt'))]:
        (out/path.name).write_bytes(path.read_bytes())
    (out/'README.txt').write_text('OFFLINE ENGINEERING ACCEPTANCE, NOT MODEL DIAGNOSIS.\n'
        'Only synthetic raw inputs/responses; public sample summary has hashes/readiness, no new raw excerpts.\n'
        'Model projection is quote-only; host provenance is synthetic and is never sent.\n',encoding='utf-8')
    files=[{'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
           for p in sorted(out.iterdir()) if p.is_file()]
    write('INDEX.json',{'code_sha':args.code_sha,'kind':'offline-engineering-not-model-diagnosis','files':files})
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.iterdir()):
            info=zipfile.ZipInfo(p.name,date_time=(2026,10,26,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for row in files:
            data=z.read(row['path']);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,
        'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))


if __name__=='__main__': main()
