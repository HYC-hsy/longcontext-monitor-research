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
        spans=[(0,head),(len(text)-(limit-head),len(text))]
        spans=[(a,b) for a,b in spans if b>a]
    else:
        spans=[]
    omitted=[];end=0
    for start,stop in spans:
        if start>end:omitted.append([end,start])
        end=stop
    if end<len(text):omitted.append([end,len(text)])
    return {'segments':[{'start':a,'end':b,'text':text[a:b]} for a,b in spans],
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
                for key,value in result.items():
                    if key in meta['identity_fields']:continue
                    parsed=value
                    if key=='content' and isinstance(value,str):
                        try:parsed=json.loads(value)
                        except (ValueError,TypeError):pass
                    if key=='content' and isinstance(parsed,dict) and STREAM_KEYS.intersection(parsed):
                        for subkey,subvalue in parsed.items():
                            add(receipts,f'tool_results[{index}].content.{subkey}',subvalue,
                                'tool_receipt' if subkey in STREAM_KEYS else 'unclassified_tool_field',**meta)
                    else:
                        add(receipts,f'tool_results[{index}].{key}',value,'tool_receipt',**meta)
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
    rows=[];seen_receipts=set()
    for entries,limits in ((actions,action_limits),(receipts,receipt_limits),(actors,actor_limits),(context,context_limits)):
        for entry,limit in zip(entries,limits):
            text=entry['text'];entry={k:v for k,v in entry.items() if k!='text'}
            index=entry.get('receipt_index')
            if index is not None:
                if index in seen_receipts:
                    for key in ('identity_fields','paired_command_indices','pairing'):entry.pop(key,None)
                seen_receipts.add(index)
            rows.append({**entry,**excerpt(text,limit)})
    if rows:rows[0].update(projection='head_tail_original_ranges',source_event_text_budget=budget)
    return rows


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
