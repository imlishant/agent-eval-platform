import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { NestExpressApplication } from '@nestjs/platform-express';
import { existsSync } from 'fs';
import { join } from 'path';
import { AppModule } from './app.module';
import { REPO, WEB_DIST } from './paths';

async function bootstrap() {
  const envFile = join(REPO, '.env');
  if (existsSync(envFile)) process.loadEnvFile(envFile); // API keys for the runner; never logged
  const app = await NestFactory.create<NestExpressApplication>(AppModule);
  app.setGlobalPrefix('api');
  app.enableShutdownHooks();
  if (existsSync(WEB_DIST)) {
    // serve the built Vue UI from the same port (one container, one URL)
    app.useStaticAssets(WEB_DIST);
    app.use((req: any, res: any, next: any) =>
      req.method === 'GET' && !req.path.startsWith('/api') ? res.sendFile(join(WEB_DIST, 'index.html')) : next());
  }
  const port = Number(process.env.PORT ?? 3000);
  await app.listen(port);
  console.log(`API on http://localhost:${port}/api`);
}
bootstrap();
