/**
 * ContentService — Stage 5: Content Transformation
 *
 * Responsible for:
 *  - Reformatting articles for each publication channel (web, RSS, newsletter, social)
 *  - Applying editorial style rules (headline casing, excerpt generation)
 *  - Translating content if multi-language output is required
 *  - SEO metadata generation (meta description, OG tags, structured data)
 *
 * 🔧 TODO:
 *  - Define channel-specific templates in /backend/config/channels.ts
 *  - Integrate translation provider (DeepL, Google Translate) for multi-lang
 *  - Add SEO scoring (e.g. keyword density, readability)
 */

import { Request, Response } from "express";
import { BaseService } from "../shared/utils/BaseService";
import type { PublicationChannel } from "../../shared/types/models";

class ContentService extends BaseService {
  constructor() {
    super({
      name: "content-service",
      port: Number(process.env.CONTENT_SERVICE_PORT) || 3005,
      dependencies: {
        "nlp-service": process.env.NLP_SERVICE_URL || "http://localhost:3004",
      },
    });
  }

  protected registerRoutes(): void {
    // POST /transform  body: { article_id, channels: PublicationChannel[] }
    this.app.post("/transform", this.asyncRoute(this.transformArticle.bind(this)));
  }

  private async transformArticle(req: Request, res: Response) {
    const { article_id, channels } = req.body as {
      article_id: string;
      channels: PublicationChannel[];
    };

    // TODO: fetch article, apply per-channel templates, return transformed payloads
    const result = {
      article_id,
      transformed: channels.map((channel) => ({
        channel,
        payload: null, // TODO: channel-specific output
      })),
    };
    this.ok(res, result);
  }
}

new ContentService().start();
