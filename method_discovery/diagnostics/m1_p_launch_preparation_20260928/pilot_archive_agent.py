"""Opt-in Harbor adapter: native execution, archive validation before cleanup."""
import hashlib
import json
from pathlib import Path

from adapters.harbor_ga_agent import HarborGenericAgent


class PilotArchiveAgent(HarborGenericAgent):
    def __init__(self, *args, pilot_archive_pause_path, **kwargs):
        super().__init__(*args, **kwargs)
        if self.max_turns != 300 or not self.monitor_enabled or self.monitor_config != 'claude_monitor_opus48' or self.llm_config_name != 'native_claude_cc_vibe_opus48':
            raise ValueError('pilot final adapter parameters do not match the frozen common configuration')
        self._pilot_pause = Path(pilot_archive_pause_path)
        self._pilot_run_started = False
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / 'pilot_final_adapter.json').write_text(json.dumps(dict(
            max_turns=self.max_turns, monitor_enabled=self.monitor_enabled,
            monitor_config=self.monitor_config, llm_config_name=self.llm_config_name,
            baseline_condition=self.baseline_condition), indent=2))

    async def setup(self, environment):
        original_stop = environment.stop

        async def guarded_stop(delete):
            try:
                receipt = await self._pilot_archive(environment)
                (self.logs_dir / 'pilot_archive_receipt.json').write_text(json.dumps(receipt, indent=2))
            except BaseException as error:
                failure = dict(status='archive_failed_containers_retained', run_id=self.run_id,
                               error_type=type(error).__name__, error=str(error),
                               session_id=environment.session_id)
                self._pilot_pause.parent.mkdir(parents=True, exist_ok=True)
                self._pilot_pause.write_text(json.dumps(failure, indent=2))
                self.logs_dir.mkdir(parents=True, exist_ok=True)
                (self.logs_dir / 'pilot_archive_failure.json').write_text(json.dumps(failure, indent=2))
                raise
            # No deletion is attempted until archive validation actually succeeds.
            return await original_stop(delete=delete)

        environment.stop = guarded_stop
        return await super().setup(environment)

    async def run(self, instruction, environment, context):
        self._pilot_run_started = True
        return await super().run(instruction, environment, context)

    async def _pilot_archive(self, environment):
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if environment.capabilities.mounted:
            await environment.prepare_logs_for_host()
        else:
            await environment.download_dir(source_dir='/logs/agent', target_dir=self.logs_dir)
        monitor = self.logs_dir / 'monitor'
        required = ['monitor_private/working.md', 'monitor_private/audit/dialogue.jsonl',
                    'monitor_private/audit/progress.jsonl', 'monitor_private/audit/reviews.jsonl',
                    'monitor_private/audit/provider_history.json',
                    'monitor_private/audit/request_attempts.jsonl',
                    'monitor_private/audit/provider_usage.jsonl', 'runtime_receipts.jsonl']
        if self._pilot_run_started:
            missing = [name for name in required if not (monitor / name).is_file()]
            if missing:
                raise RuntimeError('required Monitor originals missing before cleanup: ' + ', '.join(missing))
        files = [dict(path=p.relative_to(self.logs_dir).as_posix(), bytes=p.stat().st_size,
                      sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in sorted(self.logs_dir.rglob('*')) if p.is_file() and p.name not in
                 ('pilot_archive_receipt.json', 'pilot_archive_failure.json')]
        return dict(status='originals_readable_before_cleanup', run_id=self.run_id,
                    run_started=self._pilot_run_started, session_id=environment.session_id,
                    files=files, semantic_verdict=None)
