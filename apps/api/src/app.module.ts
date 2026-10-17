import { Module } from '@nestjs/common';
import { ApiController } from './api.controller';
import { DbService } from './db.service';
import { ExperimentsService } from './experiments.service';
import { RunnerService } from './runner.service';
import { SchedulerService } from './scheduler.service';

@Module({
  controllers: [ApiController],
  providers: [DbService, RunnerService, SchedulerService, ExperimentsService],
})
export class AppModule {}
