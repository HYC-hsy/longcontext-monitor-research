"""Read-only public projection replay. No transport, model, profile or publishing."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import zipfile
from pma_evidence_review import claim_split as cs

ARCHIVE_SHA='a30ff99e694d645a507c1841c33960765cb3bd0baceb17369118a43855b76e25'
ARCHIVE_COMMIT='c40f191878d1c45afccba4098ba4a16c14129c2f'
ARCHIVE_PATH='pma_evidence_review/diagnostic_packages/PMA_CLAIM_SPLIT_EIGHT_REAL_TASKS_20261029.zip'


def replay(path):
    data=Path(path).read_bytes()
    assert len(data)==103996503 and hashlib.sha256(data).hexdigest()==ARCHIVE_SHA
    rows=[]
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.endswith('/gate/gate_cycles.jsonl.gz') or '-split-' not in member:
                continue
            compressed=archive.read(member)
            for line_number,line in enumerate(gzip.decompress(compressed).splitlines(),1):
                wrapper=json.loads(line)
                for op in wrapper['value']['operations']:
                    for attempt_number,a in enumerate(op.get('attempts',[])):
                        if 'split' not in a:continue
                        raw=a['split']['raw_response']
                        row={'member':member,'public_projected_line':line_number,'op_index':op['index'],
                             'attempt':attempt_number,'old_engineering_status':a['engineering_status'],
                             'old_reason':a.get('reason'), 'split_raw_sha256':hashlib.sha256(raw.encode()).hexdigest(),
                             'member_sha256':hashlib.sha256(compressed).hexdigest(),
                             'projected_line_sha256':hashlib.sha256(line).hexdigest(),
                             'archived_source_line_sha256':wrapper.get('source_line_sha256'),
                             'historical_results_modified':False,'new_model_calls':0,'published':False}
                        material=a['request']['closed_material'];content=material['original_operation']['content']
                        try:
                            claims,coverage=cs.parse_split(raw,op['index'],content)
                            row['new_split_status']='exact_anchors_valid'
                            row['uncovered_nonspace_characters']=coverage['required_characters']-coverage['covered_required_characters']
                            row['offset_corrections']=coverage['offset_corrections']
                        except (ValueError,TypeError,KeyError) as error:
                            row.update(new_split_status='parse_failure',new_reason=str(error));rows.append(row);continue
                        if 'batch' not in a:
                            row['new_batch_status']='eligible_for_batch_but_no_historical_batch_or_new_semantic_run'
                        else:
                            raw_batch=a['batch']['raw_response']
                            row['batch_raw_sha256']=hashlib.sha256(raw_batch.encode()).hexdigest()
                            try:
                                reviews,preservation=cs.parse_batch(raw_batch,claims,material['submitted_evidence'],content)
                                row.update(new_batch_status='archived_output_parses_under_v2',
                                    archived_claim_verdicts=[r['verdict'] for r in reviews],
                                    archived_decomposition_complete=preservation['decomposition_complete'])
                            except (ValueError,TypeError,KeyError) as error:
                                row.update(new_batch_status='parse_failure',new_reason=str(error))
                        rows.append(row)
    return {'archive_commit':ARCHIVE_COMMIT,'archive_path':ARCHIVE_PATH,'archive_sha256':ARCHIVE_SHA,
            'notice':'Sanitized public projection; old requests were not v2 requests. Parsing replay is not semantic reassessment or retrospective publication.',
            'counts':dict(Counter(r.get('new_batch_status',r['new_split_status']) for r in rows)),
            'old_reasons':dict(Counter(r['old_reason'] or 'ok' for r in rows)), 'rows':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();report=replay(args.archive)
    with open(args.out,'x',encoding='utf8',newline='\n') as stream:json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'counts':report['counts'],'old_reasons':report['old_reasons']}))
