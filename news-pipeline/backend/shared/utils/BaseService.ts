/**
 * BaseService
 *
 * The single base class every microservice extends.
 * Each concrete service only needs to implement the methods relevant to its
 * stage in the pipeline — everything else (HTTP, logging, error handling,
 * inter-service communication) is provided here.
 *
 * Usage:
 *   class SourceService extends BaseService {
 *     constructor() { super("source-service", 3001); }
 *     protected registerRoutes() { ... }
 *   }
 */

import express, { Application, Request, Response, NextFunction } from "express";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ServiceConfig {
  name: string;
  port: number;
  version?: string;
  /** URLs of other services this one may call */
  dependencies?: Record<string, string>;
}

export interface ServiceResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  meta?: {
    service: string;
    timestamp: string;
    request_id?: string;
  };
}

// ─── BaseService ──────────────────────────────────────────────────────────────

export abstract class BaseService {
  protected readonly app: Application;
  protected readonly config: ServiceConfig;

  constructor(config: ServiceConfig) {
    this.config = { version: "1.0.0", dependencies: {}, ...config };
    this.app = express();
    this._applyMiddleware();
    this._registerHealthRoute();
    this.registerRoutes();
    this._applyErrorHandler();
  }

  // ── Abstract — implement in each concrete service ──────────────────────────

  /**
   * Register all Express routes for this service.
   * Called automatically during construction, after middleware is set up.
   */
  protected abstract registerRoutes(): void;

  // ── Provided helpers ───────────────────────────────────────────────────────

  /**
   * Start the HTTP server.
   */
  start(): void {
    this.app.listen(this.config.port, () => {
      console.log(
        `[${this.config.name}] v${this.config.version} running on port ${this.config.port}`
      );
    });
  }

  /**
   * Send a typed success response.
   */
  protected ok<T>(res: Response, data: T, requestId?: string): void {
    const body: ServiceResponse<T> = {
      success: true,
      data,
      meta: { service: this.config.name, timestamp: new Date().toISOString(), request_id: requestId },
    };
    res.status(200).json(body);
  }

  /**
   * Send a typed error response.
   */
  protected fail(res: Response, message: string, statusCode = 500): void {
    const body: ServiceResponse = {
      success: false,
      error: message,
      meta: { service: this.config.name, timestamp: new Date().toISOString() },
    };
    res.status(statusCode).json(body);
  }

  /**
   * Call another internal service and return parsed JSON.
   * Uses native fetch (Node 18+). Replace with axios if targeting older Node.
   */
  protected async callService<T>(
    serviceKey: string,
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const baseUrl = this.config.dependencies?.[serviceKey];
    if (!baseUrl) throw new Error(`Unknown dependency: ${serviceKey}`);

    const url = `${baseUrl}${path}`;
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });

    if (!res.ok) {
      throw new Error(`[${serviceKey}] ${res.status} ${res.statusText} — ${url}`);
    }

    const json: ServiceResponse<T> = await res.json();
    if (!json.success) throw new Error(json.error ?? "Unknown service error");
    return json.data as T;
  }

  /**
   * Wrap an async route handler so unhandled promise rejections reach the
   * Express error handler automatically.
   */
  protected asyncRoute(
    fn: (req: Request, res: Response, next: NextFunction) => Promise<void>
  ) {
    return (req: Request, res: Response, next: NextFunction) => {
      fn(req, res, next).catch(next);
    };
  }

  // ── Private plumbing ───────────────────────────────────────────────────────

  private _applyMiddleware(): void {
    this.app.use(express.json());
    this.app.use(express.urlencoded({ extended: true }));
    this.app.use(this._requestLogger.bind(this));
  }

  private _requestLogger(req: Request, _res: Response, next: NextFunction): void {
    console.log(`[${this.config.name}] ${req.method} ${req.path}`);
    next();
  }

  private _registerHealthRoute(): void {
    this.app.get("/health", (_req, res) => {
      res.json({
        service: this.config.name,
        status: "ok",
        version: this.config.version,
        timestamp: new Date().toISOString(),
      });
    });
  }

  private _applyErrorHandler(): void {
    this.app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
      console.error(`[${this.config.name}] Error:`, err.message);
      const body: ServiceResponse = {
        success: false,
        error: err.message,
        meta: { service: this.config.name, timestamp: new Date().toISOString() },
      };
      res.status(500).json(body);
    });
  }
}
