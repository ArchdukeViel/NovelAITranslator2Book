import { describe, expect, it } from "vitest";

import worker, { type Env } from "../src/index";

type Stored = {
  body: Uint8Array;
  uploaded: Date;
  metadata: Record<string, string>;
  checksumSha256?: string;
  contentType?: string;
  contentEncoding?: string;
};

class FakeBucket {
  private readonly objects = new Map<string, Stored>();

  async put(key: string, body: ReadableStream | ArrayBuffer | ArrayBufferView | string | null, options?: any) {
    const current = this.objects.get(key);
    const condition = options?.onlyIf;
    if (condition?.etagDoesNotMatch === "*" && current) return null;
    if (condition?.etagMatches && (!current || etag(current.body) !== condition.etagMatches)) return null;
    const bytes = body instanceof ReadableStream
      ? new Uint8Array(await new Response(body).arrayBuffer())
      : body instanceof ArrayBuffer
        ? new Uint8Array(body)
        : ArrayBuffer.isView(body)
          ? new Uint8Array(body.buffer, body.byteOffset, body.byteLength)
          : new TextEncoder().encode(body ?? "");
    const httpMetadata = options?.httpMetadata ?? {};
    const stored: Stored = {
      body: new Uint8Array(bytes),
      uploaded: new Date(),
      metadata: { ...(options?.customMetadata ?? {}) },
      checksumSha256: options?.sha256,
      contentType: httpMetadata.contentType,
      contentEncoding: httpMetadata.contentEncoding,
    };
    this.objects.set(key, stored);
    return object(key, stored);
  }

  async head(key: string) {
    const stored = this.objects.get(key);
    return stored ? object(key, stored) : null;
  }

  async get(key: string, options?: { range?: { offset: number; length?: number } }) {
    const stored = this.objects.get(key);
    if (!stored) return null;
    const start = options?.range?.offset ?? 0;
    const end = options?.range?.length ? start + options.range.length : stored.body.length;
    const result = object(key, stored);
    const body = stored.body.slice(start, end);
    return { ...result, size: body.length, body, range: options?.range ? { offset: start, length: body.length } : undefined };
  }

  async delete(key: string) {
    this.objects.delete(key);
  }

  async list(options: { prefix?: string; delimiter?: string; limit?: number }) {
    const prefix = options.prefix ?? "";
    const keys = [...this.objects.keys()].filter((key) => key.startsWith(prefix)).sort();
    const objects = keys.map((key) => object(key, this.objects.get(key)!));
    return {
      objects: options.delimiter ? objects.filter((item) => !item.key.slice(prefix.length).includes("/")) : objects,
      delimitedPrefixes: [],
      truncated: false,
      cursor: undefined,
    };
  }
}

function etag(bytes: Uint8Array): string {
  return `"${[...bytes].map((value) => value.toString(16).padStart(2, "0")).join("").slice(0, 32)}"`;
}

function object(key: string, stored: Stored): any {
  return {
    key,
    size: stored.body.length,
    uploaded: stored.uploaded,
    httpEtag: etag(stored.body),
    httpMetadata: { contentType: stored.contentType, contentEncoding: stored.contentEncoding },
    customMetadata: stored.metadata,
    checksums: { toJSON: () => ({ sha256: stored.checksumSha256 }) },
    body: new ReadableStream({ start(controller) { controller.enqueue(stored.body); controller.close(); } }),
    writeHttpMetadata(headers: Headers) {
      if (stored.contentType) headers.set("content-type", stored.contentType);
      if (stored.contentEncoding) headers.set("content-encoding", stored.contentEncoding);
    },
  };
}

function environment(app = new FakeBucket(), backup = new FakeBucket()): Env {
  return {
    R2_APP: app as unknown as R2Bucket,
    R2_BACKUP: backup as unknown as R2Bucket,
    GATEWAY_VERSION: "v1",
    MAX_OBJECT_BYTES: "1024",
    APP_CLIENT_ID: "app-client",
    RECOVERY_CLIENT_ID: "recovery-client",
  };
}

function objectUrl(bucketClass: string, key: string): string {
  return `https://gateway.test/v1/${bucketClass}/objects/${encodeURIComponent(key)}`;
}

describe("R2 gateway contract", () => {
  it("requires Access authentication and never exposes a bucket selector", async () => {
    const env = environment();
    const unauthenticated = await worker.fetch(new Request("https://gateway.test/v1/app/objects/novels%2F1%2Fa"), env);
    expect(unauthenticated.status).toBe(401);

    const arbitrary = await worker.fetch(
      new Request("https://gateway.test/v1/not-a-bucket/objects/novels%2F1%2Fa", {
        headers: { "CF-Access-Client-Id": "app-client" },
      }),
      env,
    );
    expect(arbitrary.status).toBe(404);
  });

  it("allows application exact writes and reads only in the novels namespace", async () => {
    const env = environment();
    const url = objectUrl("app", "novels/1/chapter.json.gz");
    const put = await worker.fetch(new Request(url, {
      method: "PUT",
      headers: {
        "CF-Access-Client-Id": "app-client",
        "Content-Length": "5",
        "X-R2-Content-Type": "application/octet-stream",
        "X-R2-Meta-Logical-Sha256": "digest",
        "X-R2-Checksum-Sha256": "checksum",
      },
      body: "hello",
    }), env);
    expect(put.status).toBe(201);

    const get = await worker.fetch(new Request(url, { headers: { "CF-Access-Client-Id": "app-client" } }), env);
    expect(get.status).toBe(200);
    expect(await get.text()).toBe("hello");
    expect(get.headers.get("x-r2-meta-logical-sha256")).toBe("digest");
    expect(get.headers.get("x-r2-checksum-sha256")).toBe("checksum");

    const forbidden = await worker.fetch(new Request(objectUrl("app", "runtime/cache"), {
      headers: { "CF-Access-Client-Id": "app-client" },
    }), env);
    expect(forbidden.status).toBe(403);
  });

  it("returns bounded byte ranges with a 206 response", async () => {
    const env = environment();
    const url = objectUrl("app", "novels/1/range.txt");
    const put = await worker.fetch(new Request(url, {
      method: "PUT",
      headers: { "CF-Access-Client-Id": "app-client", "Content-Length": "6" },
      body: "abcdef",
    }), env);
    expect(put.status).toBe(201);

    const ranged = await worker.fetch(new Request(url, {
      headers: { "CF-Access-Client-Id": "app-client", Range: "bytes=1-3" },
    }), env);
    expect(ranged.status).toBe(206);
    expect(ranged.headers.get("content-length")).toBe("3");
    expect(ranged.headers.get("content-range")).toBe("bytes 1-3/*");
    expect(await ranged.text()).toBe("bcd");
  });

  it("keeps listing and backup writes on the recovery identity", async () => {
    const env = environment();
    const listAsApp = await worker.fetch(
      new Request("https://gateway.test/v1/app/list?prefix=novels%2F", {
        headers: { "CF-Access-Client-Id": "app-client" },
      }),
      env,
    );
    expect(listAsApp.status).toBe(403);

    const listAsRecovery = await worker.fetch(
      new Request("https://gateway.test/v1/app/list?prefix=novels%2F", {
        headers: { "CF-Access-Client-Id": "recovery-client" },
      }),
      env,
    );
    expect(listAsRecovery.status).toBe(200);

    const backupPut = await worker.fetch(new Request(objectUrl("backup", "snapshots/run/manifest.json"), {
      method: "PUT",
      headers: {
        "CF-Access-Client-Id": "recovery-client",
        "Content-Length": "2",
      },
      body: "{}",
    }), env);
    expect(backupPut.status).toBe(201);

    const backupAsApp = await worker.fetch(new Request(objectUrl("backup", "snapshots/run/manifest.json"), {
      headers: { "CF-Access-Client-Id": "app-client" },
    }), env);
    expect(backupAsApp.status).toBe(403);
  });

  it("rejects traversal, oversized, and failed immutable writes", async () => {
    const env = environment();
    const traversal = await worker.fetch(new Request(objectUrl("app", "novels/../secret"), {
      headers: { "CF-Access-Client-Id": "app-client" },
    }), env);
    expect(traversal.status).toBe(400);

    const oversized = await worker.fetch(new Request(objectUrl("app", "novels/1/large"), {
      method: "PUT",
      headers: { "CF-Access-Client-Id": "app-client", "Content-Length": "2048" },
      body: "x".repeat(2048),
    }), env);
    expect(oversized.status).toBe(413);

    const url = objectUrl("app", "novels/1/immutable");
    const first = await worker.fetch(new Request(url, {
      method: "PUT",
      headers: { "CF-Access-Client-Id": "app-client", "Content-Length": "1", "If-None-Match": "*" },
      body: "a",
    }), env);
    expect(first.status).toBe(201);
    const second = await worker.fetch(new Request(url, {
      method: "PUT",
      headers: { "CF-Access-Client-Id": "app-client", "Content-Length": "1", "If-None-Match": "*" },
      body: "b",
    }), env);
    expect(second.status).toBe(412);
  });
});
