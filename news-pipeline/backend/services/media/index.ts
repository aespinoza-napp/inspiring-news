/**
 * MediaService — Stage 6: Media Selection
 *
 * Responsible for:
 *  - Searching stock/editorial photo APIs for images relevant to an article
 *  - Scoring and ranking media assets by relevance
 *  - Checking and storing license information
 *  - Image optimization / resizing for different channels
 *
 * 🔧 TODO:
 *  - Integrate image providers: Unsplash, Getty, AP Images, Reuters Connect
 *  - Implement relevance scoring (CLIP embeddings or keyword match)
 *  - Add image resizing pipeline (sharp, ImageMagick)
 *  - Store MediaAssets in the shared database
 */

import { Request, Response } from "express";
import { BaseService } from "../shared/utils/BaseService";

class MediaService extends BaseService {
  constructor() {
    super({
      name: "media-service",
      port: Number(process.env.MEDIA_SERVICE_PORT) || 3006,
    });
  }

  protected registerRoutes(): void {
    // POST /select  body: { article_id, keywords: string[], count?: number }
    this.app.post("/select", this.asyncRoute(this.selectMedia.bind(this)));
    this.app.get("/assets/:id", this.asyncRoute(this.getAsset.bind(this)));
  }

  private async selectMedia(req: Request, res: Response) {
    const { article_id, keywords, count = 3 } = req.body;
    // TODO: query image APIs with keywords, rank by relevance score, return top `count`
    this.ok(res, { article_id, assets: [], count });
  }

  private async getAsset(req: Request, res: Response) {
    // TODO: fetch from DB
    this.fail(res, "Not implemented", 501);
  }
}

new MediaService().start();
