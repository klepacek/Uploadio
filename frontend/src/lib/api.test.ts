import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, json } from "./api";
const session = vi.hoisted(() => ({ getSession: vi.fn() }));
vi.mock("./supabase", () => ({ supabase: () => ({ auth: session }) }));
describe("authenticated API requests", () => {
  beforeEach(() => {
    session.getSession.mockResolvedValue({
      data: { session: { access_token: "test-token" } },
    });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });
  it("does not send a request without a session", async () => {
    session.getSession.mockResolvedValue({ data: { session: null } });
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    await expect(api("/posts")).rejects.toThrow("session expired");
    expect(fetch).not.toHaveBeenCalled();
  });
  it("sends bearer authorization and explicit consent", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ status: "scheduled" }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetch);
    await api("/posts/123/publish", json("POST", { consent: true }));
    const request = fetch.mock.calls[0][1];
    expect(request.headers.Authorization).toBe("Bearer test-token");
    expect(JSON.parse(request.body)).toEqual({ consent: true });
  });
  it("displays safe backend error messages", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Workspace not found" }), {
          status: 404,
        }),
      ),
    );
    await expect(api("/posts")).rejects.toThrow("Workspace not found");
  });
  it("handles successful deletion without parsing an empty response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );
    expect(await api("/posts/123", { method: "DELETE" })).toBeUndefined();
  });
});
