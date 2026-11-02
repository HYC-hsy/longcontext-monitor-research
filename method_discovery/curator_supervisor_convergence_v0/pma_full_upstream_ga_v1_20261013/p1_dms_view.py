"""Bounded deterministic display only; original storage and read pages unchanged."""
import json
from p1_source_archive import encode, split_visible_observation

STREAM_KEYS = {'stdout','stderr','exit_code','status','return_code','error'}


def text_value(value):
    return (value,'raw_string') if isinstance(value,str) else (encode(value),'json_value')


def excerpt(text, limit):
    limit=max(0,min(limit,len(text)))
    if limit==len(text):
        return {'text':text,'preview_only':False}
    elif limit:
        head=max(1,limit//4)
        head_end=head
        boundary=text.rfind('\n',0,head)
        if boundary>=0:head_end=boundary+1
        tail_start=len(text)-(limit-head)
        if tail_start and text[tail_start-1]!='\n':
            boundary=text.find('\n',tail_start)
            if boundary>=0 and boundary+1<len(text):tail_start=boundary+1
        spans=[(0,head_end),(tail_start,len(text))]
        spans=[(a,b) for a,b in spans if b>a]
    else:
        spans=[]
    omitted=[];end=0
    for start,stop in spans:
        if start>end:omitted.append([end,start])
        end=stop
    if end<len(text):omitted.append([end,len(text)])
    return {'segments':[{'start':a,'end':b,'text':text[a:b],
                         'starts_mid_line':a>0 and text[a-1]!='\n',
                         'ends_mid_line':b<len(text) and text[b-1]!='\n'} for a,b in spans],
            'total_characters':len(text),
            'omitted_ranges':omitted,'preview_only':limit<len(text)}


def fair_limits(entries, budget, cap=None):
    limits=[0]*len(entries)
    needs=[min(len(e['text']),cap) if cap is not None else len(e['text']) for e in entries]
    while budget>0:
        pending=[i for i,n in enumerate(needs) if limits[i]<n]
        if not pending:break
        share=max(1,budget//len(pending))
        for i in pending:
            n=min(share,needs[i]-limits[i],budget)
            limits[i]+=n;budget-=n
            if not budget:break
    return limits


def event_preview(store, source):
    sid=source['source_id'];event=store.state['events'][sid];raw=event['raw']
    original=store._fields([source])
    # Preserve the former per-source displayed-text budget.
    budget=sum(min(800,len(t)) for _,_,_,t in original)
    actions=[];receipts=[];actors=[];context=[]
    def add(rows,field,value,role,**meta):
        text,encoding=text_value(value)
        rows.append({'source_id':sid,'field':field,'role':role,'encoding':encoding,'text':text,**meta})
    if 'commands' in raw:add(actions,'commands',raw['commands'],'actions_and_parameters')
    for field in ('analysis','plan'):
        if field in raw:add(actors,field,raw[field],'actor_self_report')
    known,actor,results=split_visible_observation(raw.get('observation',''))
    if known:
        add(actors,'observation.content',actor,'actor_history')
        if not results:add(receipts,'tool_results',[],'no_tool_receipts')
        for index,result in enumerate(results):
            meta={'receipt_index':index,'identity_fields':{},'paired_command_indices':[],
                  'pairing':'unknown_or_ambiguous'}
            if isinstance(result,dict):
                meta['identity_fields']={k:result[k] for k in ('tool_use_id','tool_call_id','call_id','id') if k in result}
                for link in event['call_links']:
                    if index in link['receipts'] and link['pairing']=='explicit':
                        meta['paired_command_indices'].extend(link['commands']);meta['pairing']='explicit'
                emitted=False
                remainder={k:v for k,v in result.items() if k not in meta['identity_fields'] and k not in STREAM_KEYS and k!='content'}
                if remainder:
                    add(receipts,f'tool_results[{index}].unclassified_remainder',remainder,
                        'unclassified_tool_fields',field_count=len(remainder),**meta)
                    emitted=True
                for key,value in result.items():
                    if key in meta['identity_fields'] or key in remainder:continue
                    emitted=True
                    parsed=value
                    if key=='content' and isinstance(value,str):
                        try:parsed=json.loads(value)
                        except (ValueError,TypeError):pass
                    if key=='content' and isinstance(parsed,dict) and STREAM_KEYS.intersection(parsed):
                        for subkey in parsed:
                            if subkey in STREAM_KEYS:
                                add(receipts,f'tool_results[{index}].content.{subkey}',parsed[subkey],'tool_receipt',**meta)
                        remainder={k:v for k,v in parsed.items() if k not in STREAM_KEYS}
                        if remainder:add(receipts,f'tool_results[{index}].content.unclassified_remainder',
                                         remainder,'unclassified_tool_fields',field_count=len(remainder),**meta)
                    else:
                        add(receipts,f'tool_results[{index}].{key}',value,'tool_receipt',**meta)
                if not emitted:
                    add(receipts,f'tool_results[{index}].empty',{},'receipt_present_no_content',**meta)
            else:
                add(receipts,f'tool_results[{index}]',result,'unclassified_tool_receipt',**meta)
    else:
        add(receipts,'observation',raw.get('observation',''),'unclassified_observation')
    meta={k:v for k,v in raw.items() if k not in {'commands','observation','analysis','plan'}}
    if meta:add(context,'event_metadata',meta,'accepted_event_metadata')
    action_limits=fair_limits(actions,min(800,budget));left=budget-sum(action_limits)
    actor_reserve=min(200,sum(min(800,len(e['text'])) for e in actors))
    context_reserve=min(100,sum(min(200,len(e['text'])) for e in context))
    receipt_limits=fair_limits(receipts,max(0,left-actor_reserve-context_reserve))
    left-=sum(receipt_limits)
    actor_limits=fair_limits(actors,max(0,left-context_reserve),cap=800);left-=sum(actor_limits)
    context_limits=fair_limits(context,left,cap=200)
    entries=[];limits=[];seen_receipts=set()
    for rows,allocated in ((actions,action_limits),(receipts,receipt_limits),(actors,actor_limits),(context,context_limits)):
        for entry,limit in zip(rows,allocated):
            entry=dict(entry)
            index=entry.get('receipt_index')
            if index is not None:
                if index in seen_receipts:
                    for key in ('identity_fields','paired_command_indices','pairing'):entry.pop(key,None)
                seen_receipts.add(index)
            # Prefer whole short stdout/stderr without keyword inspection.
            if entry['field'].endswith(('.stdout','.stderr')) and len(entry['text'])<=2048:
                limit=len(entry['text'])
            entries.append(entry);limits.append(limit)
    old=[{'source_id':x,'field':f,'encoding':e,'text':t[:800],
          'shown_characters':min(800,len(t)),'total_characters':len(t),'preview_only':len(t)>800}
         for x,f,e,t in original]
    cap=len(encode(old))+512
    receipt_count=len(results) if known else None
    def render(count):
        kept=[i for i in range(count) if limits[i]>0 or not entries[i]['text']]
        visible_receipts={entries[i]['receipt_index'] for i in kept if 'receipt_index' in entries[i]}
        omitted=[i for i in range(len(entries)) if i not in kept]
        ranges=[]
        for i in omitted:
            if ranges and ranges[-1][1]==i:ranges[-1][1]=i+1
            else:ranges.append([i,i+1])
        omitted_roles={}
        for i in omitted:
            role=entries[i]['role'];omitted_roles[role]=omitted_roles.get(role,0)+1
        header={'source_id':sid,'field':'projection_metadata','role':'projection_metadata',
                'via':source['via'],'original_read_not_implied':True,'order_basis':'host_acceptance',
                'serialized_limit':cap,'source_event_text_budget':budget,
                'receipt_count':receipt_count,'omitted_row_ranges':ranges,'omitted_roles':omitted_roles,
                'unclassified_field_count':sum(e.get('field_count',0) for e in entries),
                'unshown_receipt_count':None if receipt_count is None else receipt_count-len(visible_receipts),
                'raw_read':'memory_read_source(current_group_M_alias, cursor)'}
        output=[header]
        for i in kept:
            entry=entries[i];limit=limits[i]
            output.append({**{k:v for k,v in entry.items() if k!='text'},**excerpt(entry['text'],limit)})
        return output
    count=min(16,len(entries))
    # Reduce lower-priority text first; then rows if metadata alone is too wide.
    def priority(i):
        e=entries[i]
        if e['role'].startswith('actor_'):return 0
        if e['role']=='accepted_event_metadata':return 1
        if e['role']=='unclassified_tool_fields':return 2
        if e['role']=='actions_and_parameters':return 3
        if len(e['text'])>128:return 4
        return 5
    def over():
        rows=render(count)
        shown=sum(len(r['text']) if 'text' in r else sum(p['end']-p['start'] for p in r.get('segments',[])) for r in rows)
        return len(encode(rows))>cap or shown>budget
    for i in sorted(range(count),key=priority):
        role=entries[i]['role']
        floor=(min(200,len(entries[i]['text'])) if role=='actions_and_parameters' else
               min(limits[i],len(entries[i]['text'])) if role=='tool_receipt' and len(entries[i]['text'])<=128 else 0)
        while limits[i]>floor and over():
            limits[i]=max(floor,limits[i]-max(32,limits[i]//4))
    while count>0 and len(encode(render(count)))>cap:count-=1
    output=render(count)
    if len(encode(output))>cap:raise ValueError('projection header exceeds serialized budget')
    return output


def material_previews(store, sources):
    rows=[]
    for source in sources:
        if source['source_id'] in store.state['events']:
            rows.extend(event_preview(store,source))
        else:
            # Preserve existing legacy/task view allocation and prefix semantics.
            for sid,field,encoding,text in store._fields([source]):
                rows.append({'source_id':sid,'field':field,'encoding':encoding,
                    'text':text[:800],'shown_characters':min(800,len(text)),
                    'total_characters':len(text),'preview_only':len(text)>800})
    return rows
