import { exports } from "cloudflare:workers";
import { afterEach, describe, expect, it } from "vitest";

const worker = exports.default;
const clientHeaders = {
  "CF-Access-Client-Id": "test-app-client",
  "CF-Access-Client-Secret": "binding-test-secret",
};
const objectKey = "novels/binding-test-v1/object.txt";

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  return worker.fetch(new Request(`http://r2-gateway.test${path}`, init));
}

afterEach(async () => {
  await request(`/v1/app/objects/${encodeURIComponent(objectKey)}`, {
    method: "DELETE",
    headers: clientHeaders,
  });
});

describe("native R2 binding gateway", () => {
  it("writes and reads an exact object through the test binding", async () => {
    const put = await request(`/v1/app/objects/${encodeURIComponent(objectKey)}`, {
      method: "PUT",
      headers: {
        ...clientHeaders,
        "X-R2-Content-Type": "text/plain",
      },
      body: "binding-payload",
    });
    expect(put.status).toBe(201);

    const get = await request(`/v1/app/objects/${encodeURIComponent(objectKey)}`, {
      headers: clientHeaders,
    });
    expect(get.status).toBe(200);
    expect(await get.text()).toBe("binding-payload");
  });

  it("rejects application listing and recovery identity misuse", async () => {
    const list = await request("/v1/app/list?prefix=novels%2F&recursive=true", {
      headers: clientHeaders,
    });
    expect(list.status).toBe(403);

    const recoveryIdentity = await request(`/v1/app/objects/${encodeURIComponent(objectKey)}`, {
      method: "PUT",
      headers: {
        "CF-Access-Client-Id": "test-recovery-client",
        "CF-Access-Client-Secret": "binding-test-secret",
        "Content-Length": "7",
      },
      body: "denied",
    });
    expect(recoveryIdentity.status).toBe(403);
  });
});
