/**
 * PublishingService — Stage 8: Publishing
 *
 * Responsible for:
 *  - Scheduling and executing publication to each channel (web CMS, RSS, social, newsletter)
 *  - Generating the public URL and persisting a Publication record
 *  - Retraction/unpublish flow
 *  - Webhook notifications to downstream consumers
 *
 * 🔧 TODO:
 *  - Implement CMS adapter (WordPress REST API, Contentful, custom)
 *  - Implement social adapters (Twitter/X API, Facebook Graph, LinkedIn)
 *  - Implement newsletter adapter (Mailchimp, SendGrid)
 *  - Add scheduled publication (bull/bullmq queue + cron)
 */

import { Request, Response } from "express";
import { BaseService } from "../shared/utils/BaseService";
import type { Publication } from "../../shared/types/models";

class PublishingService extends BaseService {
  private publications: Map<string, Publication> = new Map();

  constructor() {
    super({
      name: "publishing-service",
      port: Number(process.env.PUBLISHING_SERVICE_PORT) || 3008,
      dependencies: {
        "content-service": process.env.CONTENT_SERVICE_URL || "http://localhost:3005",
      },
    });
  }

  protected registerRoutes(): void {
    // POST /publish  body: { article_id, channels, publish_date? }
    this.app.post("/publish", this.asyncRoute(this.publish.bind(this)));
    this.app.get("/publications", this.asyncRoute(this.listPublications.bind(this)));
    // DELETE /publications/:id  → retract
    this.app.delete("/publications/:id", this.asyncRoute(this.retract.bind(this)));
  }

  private async publish(req: Request, res: Response) {
    const { article_id, channels, publish_date } = req.body;
    // TODO: for each channel, call content-service to get transformed payload,
    //       then dispatch to the channel adapter and record the Publication
    const pub: Partial<Publication> = {
      id: crypto.randomUUID(),
      channel: channels[0],
      publish_date: publish_date ?? new Date().toISOString(),
      status: "scheduled",
      published_url: null,
    };
    this.ok(res, pub);
  }

  private async listPublications(_req: Request, res: Response) {
    this.ok(res, Array.from(this.publications.values()));
  }

  private async retract(req: Request, res: Response) {
    // TODO: call channel adapter to unpublish, update status → "retracted"
    this.ok(res, { retracted: req.params.id });
  }
}

new PublishingService().start();
