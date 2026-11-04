import { describe, expect, it } from "vitest";
import { dateLabel, json, statusLabel } from "./api";
describe("publishing presentation", () => {
  it("distinguishes an inbox upload from publication", () => {
    expect(statusLabel("draft_uploaded")).toBe("draft uploaded");
    expect(statusLabel("published")).toBe("published");
  });
  it("serializes explicit consent", () => {
    expect(JSON.parse(json("POST", { consent: true }).body as string)).toEqual({
      consent: true,
    });
  });
  it("handles unscheduled posts", () => {
    expect(dateLabel(null)).toBe("—");
  });
});
