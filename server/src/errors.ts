/**
 * Every error the API returns has this shape:
 *
 *   { "error": { "code": "phase_closed", "message": "...", "details": { ... } } }
 *
 * `code` is stable and meant for clients to branch on. `message` is for
 * people reading logs. `details` is optional and code-specific.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const badRequest = (code: string, message: string, details?: Record<string, unknown>) =>
  new ApiError(400, code, message, details);

export const unauthorized = (message = "Sign in first: send Authorization: Bearer <token>.") =>
  new ApiError(401, "unauthorized", message);

export const forbidden = (code: string, message: string) => new ApiError(403, code, message);

export const notFound = (code: string, message: string) => new ApiError(404, code, message);

/** The request is valid, but not at this point in the week (or not for this person). */
export const conflict = (code: string, message: string, details?: Record<string, unknown>) =>
  new ApiError(409, code, message, details);

export const unprocessable = (code: string, message: string, details?: Record<string, unknown>) =>
  new ApiError(422, code, message, details);

export const tooMany = (code: string, message: string, details?: Record<string, unknown>) =>
  new ApiError(429, code, message, details);

export const unavailable = (code: string, message: string, details?: Record<string, unknown>) =>
  new ApiError(503, code, message, details);
