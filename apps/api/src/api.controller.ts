import { BadRequestException, Body, Controller, Get, Header, Param, ParseIntPipe, Post } from '@nestjs/common';
import { CreateExperiment, ExperimentsService } from './experiments.service';
import { RunnerService } from './runner.service';
import { SchedulerService } from './scheduler.service';

@Controller()
export class ApiController {
  constructor(
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
}
