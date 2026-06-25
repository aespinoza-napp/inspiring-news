/**
 * QAService — Stage 7: Quality Assurance
 *
 * Responsible for:
 *  - Running automated checks before publication (grammar, style, completeness)
 *  - Enforcing editorial policies (prohibited topics, language standards)
 *  - Human-in-the-loop review queue for flagged articles
 *  - Approving or rejecting articles, updating status → "qa_passed" | "rejected"
 *
 * 🔧 TODO:
 *  - Integrate grammar/spell checker (LanguageTool, Grammarly API)
 *  - Define editorial policy rules in /backend/config/editorial-policies.ts
 *  - Build the human review queue UI (frontend/app/qa)
 */

import { Request, Response } from "express";
import { BaseService } from "../shared/utils/BaseService";

class QAService extends BaseService {
  constructor() {
    super({
      name: "qa-service",
      port: Number(process.env.QA_SERVICE_PORT) || 3007,
    });
  }

  protected registerRoutes(): void {
    // POST /check/:articleId   → run automated QA
    this.app.post("/check/:articleId", this.asyncRoute(this.runChecks.bind(this)));
    // PATCH /review/:articleId body: { approved: boolean, notes?: string }
    this.app.patch("/review/:articleId", this.asyncRoute(this.humanReview.bind(this)));
    // GET  /queue              → list articles pending human review
    this.app.get("/queue", this.asyncRoute(this.getQueue.bind(this)));
  }

  private async runChecks(req: Request, res: Response) {
    const { articleId } = req.params;
    // TODO: grammar check, policy check, completeness check
    this.ok(res, { article_id: articleId, passed: true, issues: [] });
  }

  private async humanReview(req: Request, res: Response) {
    const { articleId } = req.params;
    const { approved, notes } = req.body;
    // TODO: persist decision, update article status
    this.ok(res, { article_id: articleId, approved, notes });
  }

  private async getQueue(_req: Request, res: Response) {
    // TODO: fetch articles with status requiring human review from DB
    this.ok(res, []);
  }
}

new QAService().start();
