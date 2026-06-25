/**
 * SourceService  — Stage 1: Source Management
 *
 * Responsible for:
 *  - CRUD on news sources
 *  - Periodic health checks / reputation polling
 *  - Bias and reputation scoring (external or manual)
 *
 * 🔧 TODO: replace the in-memory store with a real DB call (see
 *    backend/shared/database/) and wire up the scheduler for periodic checks.
 */

import { Request, Response } from "express";
import { BaseService } from "../shared/utils/BaseService";
import type { Source } from "../../shared/types/models";

class SourceService extends BaseService {
  // TODO: replace with database repository
  private sources: Map<string, Source> = new Map();

  constructor() {
    super({
      name: "source-service",
      port: Number(process.env.SOURCE_SERVICE_PORT) || 3001,
      version: "1.0.0",
    });
  }

  protected registerRoutes(): void {
    this.app.get("/sources", this.asyncRoute(this.listSources.bind(this)));
    this.app.post("/sources", this.asyncRoute(this.createSource.bind(this)));
    this.app.get("/sources/:id", this.asyncRoute(this.getSource.bind(this)));
    this.app.patch("/sources/:id", this.asyncRoute(this.updateSource.bind(this)));
    this.app.delete("/sources/:id", this.asyncRoute(this.deleteSource.bind(this)));
  }

  // ── Handlers ──────────────────────────────────────────────────────────────

  private async listSources(req: Request, res: Response) {
    const all = Array.from(this.sources.values());
    this.ok(res, all);
  }

  private async createSource(req: Request, res: Response) {
    const source: Source = { ...req.body, id: crypto.randomUUID(), last_checked: new Date().toISOString() };
    this.sources.set(source.id, source);
    this.ok(res, source);
  }

  private async getSource(req: Request, res: Response) {
    const source = this.sources.get(req.params.id);
    if (!source) return this.fail(res, "Source not found", 404);
    this.ok(res, source);
  }

  private async updateSource(req: Request, res: Response) {
    const existing = this.sources.get(req.params.id);
    if (!existing) return this.fail(res, "Source not found", 404);
    const updated = { ...existing, ...req.body };
    this.sources.set(updated.id, updated);
    this.ok(res, updated);
  }

  private async deleteSource(req: Request, res: Response) {
    this.sources.delete(req.params.id);
    this.ok(res, { deleted: req.params.id });
  }
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
new SourceService().start();
