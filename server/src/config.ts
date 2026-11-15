import { ApiError } from "./errors";

/** Bindings and variables the Worker receives (wrangler.toml, secrets, --var). */
export interface Env {
  DB: D1Database;
  /** "development" only when started by `npm run dev`; anything else is production. */
  ENVIRONMENT?: string;
  /** "email" (production) or DEV_SIGNIN_CODES_IN_RESPONSE (local development only). */
  SIGNIN_CODE_DELIVERY?: string;
  /** "anthropic" (production) or DEV_FAKE_AI (local development only). */
  AI_MODE?: string;
  /** Secret. Required for every /v1/admin call. */
  ADMIN_SECRET?: string;
  /** Secret. Required for the AI jobs. Locally it comes from .dev.vars. */
  ANTHROPIC_API_KEY?: string;
}

/**
 * The two development modes. The values are long and shouty on purpose: they
 * show up in config, logs and response headers, and nobody should be able to
 * read either one as a production setting.
 */
export const DEV_SIGNIN_CODES_IN_RESPONSE = "INSECURE_DEV_RETURN_CODE_IN_RESPONSE";
export const DEV_FAKE_AI = "DEV_FAKE_AI_NOT_REAL";

export interface Config {
  environment: "production" | "development";
  signinDelivery: "email" | "dev-response";
  aiMode: "anthropic" | "dev-fake";
  /** Non-empty when any development mode is on; sent as a response header. */
  insecureModes: string[];
}

/**
 * Reads and checks configuration on every request. A development mode in a
 * non-development environment is a hard failure (500 server_misconfigured on
 * every route), so a deploy that somehow carries one cannot serve traffic.
 */
export function readConfig(env: Env): Config {
  const environment = env.ENVIRONMENT === "development" ? "development" : "production";

  const delivery = env.SIGNIN_CODE_DELIVERY ?? "email";
  let signinDelivery: Config["signinDelivery"];
  if (delivery === "email") signinDelivery = "email";
  else if (delivery === DEV_SIGNIN_CODES_IN_RESPONSE) signinDelivery = "dev-response";
  else throw misconfigured(`SIGNIN_CODE_DELIVERY has an unknown value.`);

  const ai = env.AI_MODE ?? "anthropic";
  let aiMode: Config["aiMode"];
  if (ai === "anthropic") aiMode = "anthropic";
  else if (ai === DEV_FAKE_AI) aiMode = "dev-fake";
  else throw misconfigured(`AI_MODE has an unknown value.`);

  const insecureModes: string[] = [];
  if (signinDelivery === "dev-response") insecureModes.push("signin-codes-in-responses");
  if (aiMode === "dev-fake") insecureModes.push("fake-ai");

  if (insecureModes.length > 0 && environment !== "development") {
    throw misconfigured(
      `Development mode (${insecureModes.join(", ")}) is set while ENVIRONMENT is not "development". Refusing to serve.`,
    );
  }
  return { environment, signinDelivery, aiMode, insecureModes };
}

function misconfigured(message: string) {
  return new ApiError(500, "server_misconfigured", message);
}
