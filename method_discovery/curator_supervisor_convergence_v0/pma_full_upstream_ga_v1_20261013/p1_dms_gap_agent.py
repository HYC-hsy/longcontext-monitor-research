"""Independent raw-material selector with a generated unresolved-item index."""
from copy import deepcopy
from p1_dms_agent import DMSP1Agent, DMSMaterialStore, SYSTEM as MATERIAL_SYSTEM

CANDIDATE = 'dms-gap-index-v1'
PENDING_MAX_CHARS = 240
SYSTEM = MATERIAL_SYSTEM.replace(
    'Select useful task requirements and complete visible events, and organize related\nmaterial into knowledge, procedural or gap groups. Use only the three memory tools.\nDo not write summaries, titles, success labels, plans or a new completion status.',
    'Maintain useful task requirements and complete visible events incrementally.\nKeep still-useful old entries; change them only when new material calls for it.\nUse only the three memory tools. Knowledge and procedural groups contain selected\noriginal material, without generated summaries, titles or success labels. Do not\nwrite a new completion status.').replace(
    'A gap means you selected material for later confirmation, not proven failure.\nSelect the smallest useful groups without dropping necessary related material.',
    'A gap is a task-relevant condition still to satisfy or a question still to answer.\nFor a gap only, write one short pending sentence and select its related material.\nThis generated unresolved index is not a fact, failure log, cause guess or plan.\nClose only the same unresolved item: observing failure or clearing a prerequisite\ndoes not satisfy the remaining goal. Keep factual experiences as original material.\nWhen new observations limit an older explanation, group the related material\ntogether rather than keeping an unverified explanation as an isolated known fact.\nSelect the smallest useful groups without dropping necessary related material.')


class GapIndexMaterialStore(DMSMaterialStore):
    candidate_name = CANDIDATE

    def _read_fields(self, target, sources):
        fields = super()._read_fields(target, sources)
        # Persisted JSON sorts object keys; keep page order stable before/after reopening.
        order = {s['source_id']:i for i,s in enumerate(sources)}
        fields.sort(key=lambda row:(order[row[0]], row[1]!='directory', row[1]))
        group = self.state['groups'].get(target.get('id'))
        if group and group['category'] == 'gap':
            fields.insert(0, (target['id'], 'generated_unresolved_index_not_fact',
                              'raw_string', group['pending']))
        return fields


class GapIndexP1Agent(DMSP1Agent):
    maintenance_system = SYSTEM
    input_tail = ('\nKeep useful original materials with the three tools. No new status or factual conclusions; '
                  'only gap may add a short pending index.\n')
    store_type = GapIndexMaterialStore

    def get_tools_schema(self):
        tools = deepcopy(super().get_tools_schema())
        keep = tools[0]['function']
        keep['description'] = ('Keep selected original materials. For gap only, add one short '
                               'pending condition or question; it is a generated unresolved index, not a fact or plan.')
        keep['parameters']['properties']['pending'] = {
            'type': 'string', 'minLength': 1, 'maxLength': PENDING_MAX_CHARS,
            'description': 'Required only for gap: one short unresolved condition or question. Forbidden for other categories.'}
        return tools

    def _valid_keep(self, args):
        if (not isinstance(args, dict) or not isinstance(args.get('category'),str)
                or args['category'] not in {'knowledge','procedural','gap'}):
            return False
        if args['category'] != 'gap':
            return super()._valid_keep(args)
        text = args.get('pending')
        return (set(args) == {'category','source_ids','pending'} and isinstance(text,str)
                and bool(text.strip()) and len(text) <= PENDING_MAX_CHARS)

    def _group_metadata(self, args):
        group = super()._group_metadata(args)
        if args['category'] == 'gap':
            group.update(pending=args['pending'], index_kind='generated_unresolved_index_not_fact')
        return group

    def _group_label(self, key):
        group = self.links.state['groups'][key]
        if group['category'] == 'gap':
            return {'generated_unresolved_index': {'text': group['pending'],
                    'kind': group['index_kind']}}
        return {}
