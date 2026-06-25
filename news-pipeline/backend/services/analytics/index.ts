/**
 * AnalyticsService — Stage 9: Analytics & Feedback
 *
 * Responsible for:
 *  - Ingesting page-view / engagement events from the frontend
 *  - Aggregating article metrics (views, reads, shares, bounce rate)
 *  - Feeding performance data back into source reputation scores
 *  - Providing dashboard data to the frontend analytics page
 *
 * 🔧 TODO:
 *  - Decide on event ingestion strategy: direct API vs event bus (Kafka, RabbitMQ)
 *  - Integrate analytics DB (ClickHouse, TimescaleDB, or BigQuery for scale)
 *  - Build feedback loop: top-performing source patterns → source reputation update
 *  - Add A/B test tracking for headline variants
 */

import { Request, Response } from "express";
import { BaseService } from "../shared/utils/BaseService";
import type { ArticleMetrics } from "../../shared/types/models";

class AnalyticsService extends BaseService {
  private metrics: Map<string, ArticleMetrics[]> = new Map();

  constructor() {
    super({
      name: "analytics-service",
      port: Number(process.env.ANALYTICS_SERVICE_PORT) || 3009,
      dependencies: {
        "source-service": process.env.SOURCE_SERVICE_URL || "http://localhost:3001",
      },
    });
  }

  protected registerRoutes(): void {
    // POST /events  body: { article_id, event_type, ... }
    this.app.post("/events", this.asyncRoute(this.trackEvent.bind(this)));
    // GET  /metrics/:articleId
    this.app.get("/metrics/:articleId", this.asyncRoute(this.getMetrics.bind(this)));
    // GET  /dashboard  → aggregated stats for the dashboard
    this.app.get("/dashboard", this.asyncRoute(this.getDashboard.bind(this)));
  }

  private async trackEvent(req: Request, res: Response) {
    const { article_id } = req.body;
    // TODO: store event, update aggregates
    this.ok(res, { tracked: true, article_id });
  }

  private async getMetrics(req: Request, res: Response) {
    const m = this.metrics.get(req.params.articleId) ?? [];
    this.ok(res, m);
  }

  private async getDashboard(_req: Request, res: Response) {
    // TODO: aggregate across all articles and return summary stats
    this.ok(res, {
      total_articles: 0,
      total_views: 0,
      avg_credibility_score: null,
      top_sources: [],
    });
  }
}

new AnalyticsService().start();
