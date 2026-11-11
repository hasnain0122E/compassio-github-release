import { afterEach, expect, it, vi } from "vitest";
import { get, invalidate, MAX_CONCURRENT, post } from "./api";

afterEach(() => {
  invalidate();
  vi.unstubAllGlobals();
});

it("shares GETs while letting each subscriber abort independently", async () => {
  let finish!: (r: Response) => void;
  const fetcher = vi.fn(() => new Promise<Response>(resolve => { finish = resolve; }));
  vi.stubGlobal("fetch", fetcher);
  const first = get("/example_shared");
  const controller = new AbortController();
  const second = get("/example_shared", controller.signal);
  const rejected = expect(second).rejects.toMatchObject({ name: "AbortError" });
  await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  controller.abort();
  await rejected;
  finish(new Response('{"example":true}'));
  await expect(first).resolves.toEqual({ example: true });
  await expect(get("/example_shared")).resolves.toEqual({ example: true });
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it("rejects an already aborted subscriber without a request", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  const controller = new AbortController();
  controller.abort();
  await expect(get("/example_aborted", controller.signal)).rejects.toMatchObject({ name: "AbortError" });
  expect(fetcher).not.toHaveBeenCalled();
});

it("caps a burst of real fetch calls and releases every queued slot", async () => {
  let active = 0;
  let peak = 0;
  vi.stubGlobal("fetch", vi.fn(async () => {
    active++;
    peak = Math.max(peak, active);
    await new Promise(resolve => setTimeout(resolve, 5));
    active--;
    return new Response('{}');
  }));
  const results = await Promise.all(Array.from({ length: 17 }, (_, i) => post(`/example_queue/${i}`, {})));
  expect(results).toHaveLength(17);
  expect(peak).toBe(MAX_CONCURRENT);
  expect(active).toBe(0);
});

it("invalidating cached GETs obtains fresh evidence", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response('{"revision":1}')).mockResolvedValueOnce(new Response('{"revision":2}'));
  vi.stubGlobal("fetch", fetcher);
  await expect(get("/example_revision")).resolves.toEqual({ revision: 1 });
  invalidate();
  await expect(get("/example_revision")).resolves.toEqual({ revision: 2 });
  expect(fetcher).toHaveBeenCalledTimes(2);
});
