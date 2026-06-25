/**
 * NLPService — Stage 4a: Content Enrichment (NLP)
 *
 * Responsible for:
 *  - Named entity recognition (NER)
 *  - Sentiment analysis → sentiment_score
 *  - Keyword extraction → keywords[]
 *  - Automatic summarization → summary
 *  - Language detection / translation if needed
 *
 * 🔧 TODO:
 *  - Integrate an NLP provider: OpenAI, Hugging Face, spaCy (via Python sidecar),
 *    AWS Comprehend, or Google Natural Language API
 *  - Define confidence thresholds for entity types
 *  - Implement language detection (e.g. franc, langdetect)
 */

import { Request, Response } from "express";
import { BaseService } from "../shared/utils/BaseService";

class NLPService extends BaseService {
  constructor() {
    super({
      name: "nlp-service",
      port: Number(process.env.NLP_SERVICE_PORT) || 3004,
    });
  }

  protected registerRoutes(): void {
    // POST /analyze  body: { text: string }
    this.app.post("/analyze", this.asyncRoute(this.analyzeText.bind(this)));
  }

  private async analyzeText(req: Request, res: Response) {
    const { text } = req.body as { text: string };
    if (!text) return this.fail(res, "text is required", 400);

    // TODO: call NLP provider and return real values
    const result = {
      sentiment_score: null,  // TODO
      keywords: [],           // TODO
      entities: [],           // TODO
      summary: null,          // TODO
      language: null,         // TODO
    };
    this.ok(res, result);
  }
}

new NLPService().start();
