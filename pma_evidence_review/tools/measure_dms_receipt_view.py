"""Offline public-archive reconstruction, not original run manifests or model calls."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import patch
import zipfile
from run_p1_source_case import ROOT, BankDisplayAgent
from p1_dms_agent import DMSP1Agent
from p1_dms_view import material_previews


def old_preview(store,sources):
    return [{'source_id':sid,'field':field,'encoding':encoding,'text':text[:800],
             'shown_characters':min(800,len(text)),'total_characters':len(text),'preview_only':len(text)>800}
            for sid,field,encoding,text in store._fields(sources)]


def measure(archive):
    output=[]
    with zipfile.ZipFile(archive) as z:
        members=sorted(n for n in z.namelist() if n.startswith('real/B/') and n.endswith('/source_archive/source_links.json'))
        if len(members)!=6:raise ValueError('expected exactly six B archives')
        for member in members:
            wrapped=json.loads(z.read(member));data=wrapped.get('data',wrapped)
            with tempfile.TemporaryDirectory() as tmp:
                a=DMSP1Agent(task=data['task'],task_id=data['task_id'],source_root=tmp,
                    memory=BankDisplayAgent.load_bank(data['bank']),llm=NS(call=None))
                state=deepcopy(a.links.state)
                # Never copy the archive cursor secret or unknown/private fields.
                for key in state:
                    if key!='secret' and key in data:state[key]=deepcopy(data[key])
                a.links.commit(state)
                prefix=member.rsplit('source_links.json',1)[0]
                reconstructed=[]
                for legacy in state['legacy_snapshots'].values():
                    ref=legacy.get('old_source') or {};wid=ref.get('context_window')
                    if wid:
                        path=prefix+'windows/'+wid+'.json'
                        if path in z.namelist():
                            out=a.source_archive.window_path(wid);out.parent.mkdir(exist_ok=True);out.write_bytes(z.read(path))
                            public_hash=hashlib.sha256(out.read_bytes()).hexdigest()
                            if public_hash!=ref.get('context_sha256'):
                                reconstructed.append({'window_id':wid,'recorded_original_sha256':ref.get('context_sha256'),
                                    'public_projection_sha256':public_hash,'scope':'temporary public-projection reconstruction, not production binding'})
                                ref['context_sha256']=public_hash
                a.links.commit(state)
                with patch('p1_dms_agent.material_previews',old_preview):
                    before=a._input('',1,[])[0]
                after=a._input('',1,[])[0]
                sources={s['source_id'] for ref in state['refs'].values() for s in ref.get('sources',[]) if s['source_id'] in state['events']}
                visibility=[]
                # Expectations are measurement assertions, never algorithm rules.
                expected={'event_7':'command not found'} if '/01-' in member else {'event_8':'Segmentation fault'} if '/04-' in member else {}
                for sid,phrase in expected.items():
                    old=old_preview(a.links,[{'source_id':sid,'via':'selected'}])
                    new=material_previews(a.links,[{'source_id':sid,'via':'selected'}])
                    visibility.append({'source_id':sid,'selected':sid in sources,
                        'expected_fixture_text':phrase,'before':phrase in json.dumps(old,ensure_ascii=False),
                        'after_receipts':phrase in json.dumps([r for r in new if 'receipt' in r.get('role','')],ensure_ascii=False)})
                output.append({'case':member.split('/')[2],
                    'context':'public-projection reconstructed next maintenance; final stored bank; no new trajectory events',
                    'public_context_rebindings':reconstructed,
                    'before_characters':len(before),'after_characters':len(after),'delta_characters':len(after)-len(before),
                    'before_utf8_bytes':len(before.encode()),'after_utf8_bytes':len(after.encode()),
                    'delta_utf8_bytes':len(after.encode())-len(before.encode()),'selected_event_count':len(sources),
                    'visibility':visibility,'real_model_calls':0})
    return {'archive_sha256':hashlib.sha256(Path(archive).read_bytes()).hexdigest(),'cases':output}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('preserve previous measurements')
    result=measure(args.archive);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
