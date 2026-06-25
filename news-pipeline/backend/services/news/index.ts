/**
 * NewsService — Stage 2: News Collection
 *
 * Responsible for:
 *  - Fetching articles from registered sources (RSS, API, scraping)
 *  - Deduplication (URL + content hash)
 *  - Storing raw articles with status = "raw"
 *
 * 🔧 TODO:
 *  - Implement RSS parser (e.g. rss-parser)
 *  - Implement scraping adapter (e.g. Puppeteer / Playwright)
 *  - Schedule periodic polling via cron or a message queue
 *  - Store to DB instead of in-memory map
 */

import { Request, Response } from "express";
import { BaseService } from "../shared/utils/BaseService";
import type { NewsArticle } from "../../shared/types/models";

class NewsService extends BaseService {
  private articles: Map<string, NewsArticle> = new Map();

  constructor() {
    super({
      name: "news-service",
      port: Number(process.env.NEWS_SERVICE_PORT) || 3002,
      dependencies: {
        "source-service": process.env.SOURCE_SERVICE_URL || "http://localhost:3001",
      },
    });
  }

  protected registerRoutes(): void {
    this.app.get("/articles", this.asyncRoute(this.listArticles.bind(this)));
    this.app.post("/articles", this.asyncRoute(this.ingestArticle.bind(this)));
    this.app.get("/articles/:id", this.asyncRoute(this.getArticle.bind(this)));
    // Trigger a manual crawl of all active sources
    this.app.post("/collect", this.asyncRoute(this.triggerCollection.bind(this)));
  }

  private async listArticles(req: Request, res: Response) {
    const status = req.query.status as string | undefined;
    let all = Array.from(this.articles.values());
    if (status) all = all.filter((a) => a.status === status);
    this.ok(res, all);
  }

  private async ingestArticle(req: Request, res: Response) {
    const article: NewsArticle = {
      ...req.body,
      id: crypto.randomUUID(),
      status: "raw",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    this.articles.set(article.id, article);
    this.ok(res, article);
  }

  private async getArticle(req: Request, res: Response) {
    const article = this.articles.get(req.params.id);
    if (!article) return this.fail(res, "Article not found", 404);
    this.ok(res, article);
  }

  private async triggerCollection(_req: Request, res: Response) {
    // TODO: fetch active sources from source-service, crawl each one
    const sources = await this.callService("source-service", "/sources");
    this.ok(res, { message: "Collection triggered", sources_count: (sources as []).length });
  }
}

new NewsService().start();
