/**
 * FactCheckService — Stage 3: Validation & Fact Checking
 *
 * Responsible for:
 *  - Cross-referencing claims against trusted APIs (e.g. Google Fact Check, PolitiFact)
 *  - Assigning credibility_score to each article
 *  - Flagging or rejecting articles that fall below threshold
 *  - Updating article status → "validated" or "rejected"
 *
 * 🔧 TODO:
 *  - Integrate Google Fact Check Tools API
 *  - Integrate ClaimBuster or similar NLP claim detector
 *  - Define CREDIBILITY_THRESHOLD in config
 */

import { Request, Response } from "express";
import { BaseService } from "../shared/utils/BaseService";

class FactCheckService extends BaseService {
  constructor() {
    super({
      name: "fact-check-service",
      port: Number(process.env.FACT_CHECK_SERVICE_PORT) || 3003,
      dependencies: {
        "news-service": process.env.NEWS_SERVICE_URL || "http://localhost:3002",
      },
    });
  }

  protected registerRoutes(): void {
    // POST /validate/:articleId  → run fact-check on a single article
    this.app.post("/validate/:articleId", this.asyncRoute(this.validateArticle.bind(this)));
  }

  private async validateArticle(req: Request, res: Response) {
    const { articleId } = req.params;

    // TODO: fetch article, call external fact-check APIs, compute credibility_score
    // TODO: PATCH article credibility_score + status back via news-service

    const result = {
      article_id: articleId,
      credibility_score: null, // TODO
      status: "validated",     // or "rejected"
      checked_at: new Date().toISOString(),
    };
    this.ok(res, result);
  }
}

new FactCheckService().start();
