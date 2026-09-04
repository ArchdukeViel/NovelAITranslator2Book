type BucketClass = "app" | "backup";
export type IdentityClass = "application" | "recovery";
type ObjectMetadata = Record<string, string>;

const FIXED_METADATA = new Map([
  ["logical-sha256", "x-r2-meta-logical-sha256"],
  ["checksum-sha256", "x-r2-meta-checksum-sha256"],
  ["source-etag", "x-r2-meta-source-etag"],
  ["sha256", "x-r2-meta-sha256"],
]);
const APP_PREFIX = "novels/";
const BACKUP_PREFIXES = ["snapshots/", "database/", "objects/"];
const REQUEST_ID_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

function requestId(request: Request): string {
  const supplied = request.headers.get("x-request-id")?.trim();
  return supplied && REQUEST_ID_PATTERN.test(supplied)
    ? supplied
    : crypto.randomUUID();
}

function responseHeaders(
  id: string,
  contentType = "application/json",
): Headers {
  const headers = new Headers({
    "cache-control": "no-store",
    "content-type": contentType,
    "x-request-id": id,
  });
  return headers;
}

function json(
  id: string,
  status: number,
  body: Record<string, unknown>,
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: responseHeaders(id),
  });
}

function failure(id: string, status: number, code: string): Response {
  return json(id, status, { error_code: code, request_id: id });
}

function normalizeClass(value: string): BucketClass | null {
  return value === "app" || value === "backup" ? value : null;
}

function bucketFor(env: Env, bucketClass: BucketClass): R2Bucket {
  return bucketClass === "app" ? env.R2_APP : env.R2_BACKUP;
}

export function identityClassFromAccessIdentity(
  identity: CloudflareAccessIdentity | undefined,
  env: Pick<Env, "APP_CLIENT_ID" | "RECOVERY_CLIENT_ID">,
): IdentityClass | null {
  const commonName = identity?.common_name;
  if (typeof commonName !== "string") return null;
  if (commonName === env.APP_CLIENT_ID) return "application";
  if (commonName === env.RECOVERY_CLIENT_ID) return "recovery";
  return null;
}

async function authenticate(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<IdentityClass | null> {
  if (!ctx.access) return null;
  let identity = await ctx.access.getIdentity();
  if (!identity?.common_name) {
    const jwt = request.headers.get("cf-access-jwt-assertion");
    if (jwt) {
      try {
        const payload = JSON.parse(atob(jwt.split(".")[1]));
        if (
          payload.aud === ctx.access.aud &&
          typeof payload.common_name === "string"
        ) {
          identity = { common_name: payload.common_name };
        }
      } catch {
      }
    }
  }
  return identityClassFromAccessIdentity(identity, env);
}

function allowed(
  identity: IdentityClass,
  bucketClass: BucketClass,
  operation: string,
): boolean {
  if (identity === "application") {
    return (
      bucketClass === "app" &&
      ["get", "head", "put", "delete"].includes(operation)
    );
  }
  if (bucketClass === "app") return ["get", "head", "delete", "list"].includes(operation);
  return ["get", "head", "put", "delete", "list"].includes(operation);
}

function decodeKey(encoded: string): string | null {
  let key: string;
  try {
    key = decodeURIComponent(encoded);
  } catch {
    return null;
  }
  if (
    !key ||
    key.length > 1024 ||
    key.startsWith("/") ||
    key.includes("\\") ||
    key.includes("\0")
  ) {
    return null;
  }
  const parts = key.split("/");
  if (parts.some((part) => !part || part === "." || part === "..")) return null;
  return key;
}

function allowedKey(bucketClass: BucketClass, key: string): boolean {
  if (bucketClass === "app") return key.startsWith(APP_PREFIX);
  return BACKUP_PREFIXES.some((prefix) => key.startsWith(prefix));
}

function normalizePrefix(
  bucketClass: BucketClass,
  value: string | null,
): string | null {
  if (!value) return bucketClass === "app" ? APP_PREFIX : null;
  let prefix: string;
  try {
    prefix = decodeURIComponent(value);
  } catch {
    return null;
  }
  if (prefix.includes("\\") || prefix.includes("\0") || prefix.startsWith("/"))
    return null;
  if (!prefix.endsWith("/")) prefix += "/";
  if (!allowedKey(bucketClass, `${prefix}placeholder`)) return null;
  return prefix;
}

function fixedMetadata(request: Request): ObjectMetadata {
  const metadata: ObjectMetadata = {};
  for (const [name, header] of FIXED_METADATA) {
    const value = request.headers.get(header)?.trim();
    if (value) metadata[name] = value.slice(0, 256);
  }
  return metadata;
}

function httpMetadata(request: Request): R2HTTPMetadata {
  const metadata: R2HTTPMetadata = {};
  const contentType = request.headers.get("x-r2-content-type")?.trim();
  const contentEncoding = request.headers.get("x-r2-content-encoding")?.trim();
  if (contentType) metadata.contentType = contentType;
  if (contentEncoding) metadata.contentEncoding = contentEncoding;
  return metadata;
}

function conditional(request: Request): R2Conditional | undefined {
  const ifMatch = request.headers.get("if-match")?.trim();
  const ifNoneMatch = request.headers.get("if-none-match")?.trim();
  if (ifMatch && ifNoneMatch) return undefined;
  if (ifMatch) return { etagMatches: ifMatch };
  if (ifNoneMatch === "*") return { etagDoesNotMatch: "*" };
  return undefined;
}

function normalizeChecksum(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  const trimmed = value.trim();
  if (/^[0-9a-fA-F]{64}$/.test(trimmed)) {
    return trimmed.toLowerCase();
  }
  try {
    const binary = atob(trimmed);
    if (binary.length === 32) {
      let hex = "";
      for (let i = 0; i < 32; i++) {
        hex += binary.charCodeAt(i).toString(16).padStart(2, "0");
      }
      return hex;
    }
  } catch {
  }
  return trimmed;
}

function objectHeaders(object: R2Object, id: string): Headers {
  const headers = responseHeaders(
    id,
    object.httpMetadata?.contentType ?? "application/octet-stream",
  );
  object.writeHttpMetadata(headers);
  headers.set("content-length", String(object.size));
  headers.set("etag", object.httpEtag);
  headers.set("last-modified", object.uploaded.toUTCString());
  const checksum = object.checksums?.toJSON().sha256;
  if (checksum) headers.set("x-r2-checksum-sha256", checksum);
  for (const [name, header] of FIXED_METADATA) {
    const value = object.customMetadata?.[name];
    if (value) headers.set(header, value);
  }
  return headers;
}

function parseRange(value: string | null): R2Range | undefined {
  if (!value) return undefined;
  const match = /^bytes=(\d+)-(\d*)$/.exec(value.trim());
  if (!match) return undefined;
  const offset = Number(match[1]);
  if (!Number.isSafeInteger(offset)) return undefined;
  if (!match[2]) return { offset };
  const end = Number(match[2]);
  if (!Number.isSafeInteger(end) || end < offset) return undefined;
  return { offset, length: end - offset + 1 };
}

function listMetadata(object: R2Object): Record<string, unknown> {
  const metadata: ObjectMetadata = {};
  for (const name of FIXED_METADATA.keys()) {
    const value = object.customMetadata?.[name];
    if (value) metadata[name] = value;
  }
  return {
    key: object.key,
    size_bytes: object.size,
    etag: object.httpEtag,
    last_modified: object.uploaded.toISOString(),
    content_type: object.httpMetadata?.contentType ?? null,
    content_encoding: object.httpMetadata?.contentEncoding ?? null,
    checksum_sha256: object.checksums?.toJSON().sha256 ?? null,
    metadata,
  };
}

async function exactObject(
  request: Request,
  env: Env,
  id: string,
  identity: IdentityClass,
  bucketClass: BucketClass,
  key: string,
): Promise<Response> {
  const operation =
    request.method === "GET"
      ? "get"
      : request.method === "HEAD"
        ? "head"
        : request.method.toLowerCase();
  if (!allowed(identity, bucketClass, operation))
    return failure(id, 403, "operation_not_allowed");
  if (!allowedKey(bucketClass, key))
    return failure(id, 403, "key_namespace_not_allowed");
  const bucket = bucketFor(env, bucketClass);
  const started = performance.now();
  try {
    if (operation === "put") {
      const contentLength = Number(request.headers.get("content-length") ?? "");
      const maxBytes = Number(env.MAX_OBJECT_BYTES || "268435456");
      if (
        !Number.isSafeInteger(contentLength) ||
        contentLength < 0 ||
        contentLength > maxBytes
      ) {
        return failure(id, 413, "object_size_not_allowed");
      }
      if (!request.body) return failure(id, 400, "body_required");
      const putOptions: R2PutOptions = {
        onlyIf: conditional(request),
        httpMetadata: httpMetadata(request),
        customMetadata: fixedMetadata(request),
      };
      const checksum = normalizeChecksum(
        request.headers.get("x-r2-checksum-sha256"),
      );
      if (checksum) putOptions.sha256 = checksum;
      const result = await bucket.put(key, request.body, putOptions);
      if (!result) return failure(id, 412, "conditional_write_failed");
      const headers = responseHeaders(id);
      headers.set("etag", result.httpEtag);
      headers.set("content-length", String(result.size));
      return new Response(
        JSON.stringify({ etag: result.httpEtag, size_bytes: result.size }),
        { status: 201, headers },
      );
    }

    const range =
      operation === "get"
        ? parseRange(request.headers.get("range"))
        : undefined;
    const object =
      operation === "get"
        ? await bucket.get(key, range ? { range } : undefined)
        : await bucket.head(key);
    if (!object) return failure(id, 404, "object_not_found");
    const headers = objectHeaders(object, id);
    if (operation === "head")
      return new Response(null, { status: 200, headers });
    const bodyObject = object as R2ObjectBody;
    if (range && bodyObject.range) {
      const responseRange = bodyObject.range;
      const start =
        "suffix" in responseRange
          ? Math.max(0, object.size - responseRange.suffix)
          : (responseRange.offset ?? 0);
      const end = start + bodyObject.size - 1;
      headers.set("content-length", String(bodyObject.size));
      headers.set("content-range", `bytes ${start}-${end}/*`);
      return new Response(bodyObject.body, { status: 206, headers });
    }
    return new Response(bodyObject.body, { status: 200, headers });
  } finally {
    console.log(
      JSON.stringify({
        bucket_class: bucketClass,
        duration_ms: Math.round((performance.now() - started) * 100) / 100,
        operation,
        request_id: id,
      }),
    );
  }
}

async function listObjects(
  request: Request,
  env: Env,
  id: string,
  identity: IdentityClass,
  bucketClass: BucketClass,
): Promise<Response> {
  if (!allowed(identity, bucketClass, "list"))
    return failure(id, 403, "operation_not_allowed");
  const url = new URL(request.url);
  const prefix = normalizePrefix(bucketClass, url.searchParams.get("prefix"));
  if (prefix === null) return failure(id, 403, "prefix_namespace_not_allowed");
  const limit = Number(url.searchParams.get("limit") ?? "1000");
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 1000)
    return failure(id, 400, "list_limit_not_allowed");
  const recursive = url.searchParams.get("recursive") !== "false";
  const cursor = url.searchParams.get("cursor") ?? undefined;
  const started = performance.now();
  try {
    const result = await bucketFor(env, bucketClass).list({
      prefix,
      cursor,
      delimiter: recursive ? undefined : "/",
      limit,
    });
    const headers = responseHeaders(id);
    return new Response(
      JSON.stringify({
        cursor: result.truncated ? result.cursor : null,
        delimited_prefixes: recursive ? [] : result.delimitedPrefixes,
        objects: result.objects.map(listMetadata),
        truncated: result.truncated,
      }),
      { status: 200, headers },
    );
  } finally {
    console.log(
      JSON.stringify({
        bucket_class: bucketClass,
        duration_ms: Math.round((performance.now() - started) * 100) / 100,
        operation: "list",
        request_id: id,
      }),
    );
  }
}

async function route(
  request: Request,
  env: Env,
  id: string,
  identity: IdentityClass,
): Promise<Response> {
  const url = new URL(request.url);
  const prefix = `/v1/`;
  if (!url.pathname.startsWith(prefix))
    return failure(id, 404, "route_not_found");
  const remainder = url.pathname.slice(prefix.length);
  if (remainder === "health" && request.method === "GET") {
    return json(id, 200, { status: "ok", version: env.GATEWAY_VERSION });
  }
  const classMatch = /^([^/]+)\/(objects|list)(?:\/(.*))?$/.exec(remainder);
  if (!classMatch) return failure(id, 404, "route_not_found");
  const bucketClass = normalizeClass(classMatch[1]);
  if (!bucketClass) return failure(id, 404, "route_not_found");
  if (classMatch[2] === "list") {
    if (request.method !== "GET") return failure(id, 405, "method_not_allowed");
    return listObjects(request, env, id, identity, bucketClass);
  }
  if (!classMatch[3]) return failure(id, 400, "object_key_required");
  const key = decodeKey(classMatch[3]);
  if (!key) return failure(id, 400, "object_key_invalid");
  if (!["GET", "HEAD", "PUT", "DELETE"].includes(request.method))
    return failure(id, 405, "method_not_allowed");
  if (request.method === "DELETE") {
    if (
      !allowed(identity, bucketClass, "delete") ||
      !allowedKey(bucketClass, key)
    ) {
      return failure(id, 403, "operation_not_allowed");
    }
    await bucketFor(env, bucketClass).delete(key);
    return new Response(null, {
      status: 204,
      headers: responseHeaders(id, "text/plain"),
    });
  }
  return exactObject(request, env, id, identity, bucketClass, key);
}

export default {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const id = requestId(request);
    let identity: IdentityClass | null;
    try {
      identity = await authenticate(request, env, ctx);
    } catch {
      identity = null;
    }
    if (!identity) return failure(id, 401, "access_authentication_required");
    try {
      return await route(request, env, id, identity);
    } catch {
      return failure(id, 502, "r2_operation_failed");
    }
  },
} satisfies ExportedHandler<Env>;
