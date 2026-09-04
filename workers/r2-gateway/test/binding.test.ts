import { env } from "cloudflare:workers";
import { afterEach, describe, expect, it } from "vitest";

import worker from "../src/index";

const objectKey = "novels/binding-test-v1/object.txt";

async function request(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  return worker.fetch(new Request(`http://r2-gateway.test${path}`, init), env, {
    access: {
      aud: "r2-gateway-test",
      getIdentity: async () => ({ common_name: "test-app-client", sub: "" }),
    },
  } as unknown as ExecutionContext);
}

afterEach(async () => {
  await request(`/v1/app/objects/${encodeURIComponent(objectKey)}`, {
    method: "DELETE",
  });
});

describe("native R2 binding gateway", () => {
  it("writes and reads an exact object through the test binding", async () => {
    const put = await request(
      `/v1/app/objects/${encodeURIComponent(objectKey)}`,
      {
        method: "PUT",
        headers: { "X-R2-Content-Type": "text/plain" },
        body: "binding-payload",
      },
    );
    expect(put.status).toBe(201);

    const get = await request(
      `/v1/app/objects/${encodeURIComponent(objectKey)}`,
      {},
    );
    expect(get.status).toBe(200);
    expect(await get.text()).toBe("binding-payload");
  });

  it("rejects application listing for the local Access identity", async () => {
    const list = await request(
      "/v1/app/list?prefix=novels%2F&recursive=true",
      {},
    );
    expect(list.status).toBe(403);
  });
});
