import { BadRequestException, Body, Controller, Get, Header, Param, ParseIntPipe, Post, Query } from '@nestjs/common';
import { DbService } from './db.service';
import { CreateExperiment, ExperimentsService } from './experiments.service';
import { RunnerService } from './runner.service';
import { SchedulerService } from './scheduler.service';

@Controller()
export class ApiController {
  constructor(
    private readonly db: DbService,
    private readonly experiments: ExperimentsService,
    private readonly runner: RunnerService,
    private readonly scheduler: SchedulerService,
  ) {}

  @Get('health')
  health() {
    return { ok: true, running_trials: this.scheduler.busy };
  }

  /** Configs (with their content-hash IDs) and tasks available to experiments. */
  @Get('catalog')
  catalog() {
    return this.runner.catalog();
  }

  /** Define a new config (saved as configs/<name>.json; ID = hash of its content). */
  @Post('configs')
  async createConfig(@Body() body: any) {
    try {
      return await this.runner.createConfig(body);
    } catch (e: any) {
      throw new BadRequestException(e.message);
    }
  }

  /** Add an OpenAI-compatible model to the registry (configs/models.json). */
  @Post('models')
  addModel(@Body() body: any) {
    try {
      return this.runner.addModel(body);
    } catch (e: any) {
      throw new BadRequestException(e.message);
    }
  }

  /** Test a model (saved or not): one real request with a tool. */
  @Post('models/check')
  checkModel(@Body() body: any) {
    return this.runner.checkModel(body);
  }

  @Post('experiments')
  create(@Body() body: CreateExperiment) {
    return this.experiments.create(body);
  }

  @Get('experiments')
  list() {
    return this.experiments.list();
  }

  @Get('experiments/:id')
  get(@Param('id', ParseIntPipe) id: number) {
    return this.experiments.get(id);
  }

  @Get('experiments/:id/trials')
  trials(@Param('id', ParseIntPipe) id: number) {
    return this.experiments.trials(id);
  }

  @Get('experiments/:id/compare')
  compare(@Param('id', ParseIntPipe) id: number) {
    return this.experiments.compare(id);
  }

  @Post('experiments/:id/retry-invalid')
  retry(@Param('id', ParseIntPipe) id: number) {
    return this.experiments.retryInvalid(id);
  }

  @Get('experiments/:id/export.json')
  @Header('Content-Disposition', 'attachment; filename="experiment.json"')
  exportJson(@Param('id', ParseIntPipe) id: number) {
    return this.experiments.exportJson(id);
  }

  @Get('experiments/:id/export.csv')
  @Header('Content-Type', 'text/csv')
  @Header('Content-Disposition', 'attachment; filename="trials.csv"')
  exportCsv(@Param('id', ParseIntPipe) id: number) {
    return this.experiments.exportCsv(id);
  }

  @Get('trials/:id')
  trial(@Param('id', ParseIntPipe) id: number) {
    return this.experiments.trial(id);
  }

  @Get('trials/:id/memory')
  trialMemory(@Param('id', ParseIntPipe) id: number) {
    const d = this.db.db;
    const stm = d.prepare('SELECT session, seq, type, content, ts FROM memory_stm WHERE trial_id = ? ORDER BY session, seq').all(id);
    const episodes = d.prepare('SELECT session, tool_calls, findings, files_written, errors, final_answer, ts FROM memory_episodes WHERE trial_id = ? ORDER BY session').all(id) as any[];
    const semantic = d.prepare('SELECT insights, patterns, key_facts, source_episodes, ts FROM memory_semantic WHERE trial_id = ? ORDER BY id DESC LIMIT 1').get(id) as any;
    return {
      stm,
      episodes: episodes.map((e) => ({ ...e, tool_calls: JSON.parse(e.tool_calls), findings: JSON.parse(e.findings), files_written: JSON.parse(e.files_written), errors: JSON.parse(e.errors) })),
      semantic: semantic ? { insights: JSON.parse(semantic.insights), patterns: JSON.parse(semantic.patterns), key_facts: JSON.parse(semantic.key_facts), source_episodes: JSON.parse(semantic.source_episodes), ts: semantic.ts } : null,
    };
  }

  @Get('trials/:id/memory/stm')
  trialMemoryStm(@Param('id', ParseIntPipe) id: number, @Query('session') session?: string) {
    const d = this.db.db;
    if (session) {
      return d.prepare('SELECT session, seq, type, content, ts FROM memory_stm WHERE trial_id = ? AND session = ? ORDER BY seq').all(id, Number(session));
    }
    return d.prepare('SELECT session, seq, type, content, ts FROM memory_stm WHERE trial_id = ? ORDER BY session, seq').all(id);
  }

  @Get('trials/:id/memory/episodes')
  trialMemoryEpisodes(@Param('id', ParseIntPipe) id: number, @Query('session') session?: string) {
    const d = this.db.db;
    const rows = session
      ? d.prepare('SELECT session, tool_calls, findings, files_written, errors, final_answer, ts FROM memory_episodes WHERE trial_id = ? AND session = ? ORDER BY session').all(id, Number(session)) as any[]
      : d.prepare('SELECT session, tool_calls, findings, files_written, errors, final_answer, ts FROM memory_episodes WHERE trial_id = ? ORDER BY session').all(id) as any[];
    return rows.map((e) => ({ ...e, tool_calls: JSON.parse(e.tool_calls), findings: JSON.parse(e.findings), files_written: JSON.parse(e.files_written), errors: JSON.parse(e.errors) }));
  }

  @Get('trials/:id/memory/semantic')
  trialMemorySemantic(@Param('id', ParseIntPipe) id: number) {
    const row = this.db.db.prepare('SELECT insights, patterns, key_facts, source_episodes, ts FROM memory_semantic WHERE trial_id = ? ORDER BY id DESC LIMIT 1').get(id) as any;
    if (!row) return null;
    return { insights: JSON.parse(row.insights), patterns: JSON.parse(row.patterns), key_facts: JSON.parse(row.key_facts), source_episodes: JSON.parse(row.source_episodes), ts: row.ts };
  }
}
