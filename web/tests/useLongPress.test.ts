// Unit tests for the touch press-and-hold gesture.
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PointerEvent as ReactPointerEvent } from "react";
import { useLongPress } from "../src/game/useLongPress";

// A minimal synthetic React PointerEvent — only the fields the hook reads.
function ptr(x: number, y: number, opts: Partial<ReactPointerEvent> = {}): ReactPointerEvent {
  return { clientX: x, clientY: y, pointerType: "touch", button: 0, ...opts } as ReactPointerEvent;
}

describe("useLongPress", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("fires after the hold delay and suppresses the trailing click", () => {
    const onLongPress = vi.fn();
    const { result } = renderHook(() => useLongPress(onLongPress, { delay: 450 }));

    act(() => result.current.handlers.onPointerDown(ptr(10, 10)));
    act(() => vi.advanceTimersByTime(450));

    expect(onLongPress).toHaveBeenCalledTimes(1);
    // The following click should be consumed exactly once.
    expect(result.current.consumeLongPress()).toBe(true);
    expect(result.current.consumeLongPress()).toBe(false);
  });

  it("does not fire on a quick tap and lets the click through", () => {
    const onLongPress = vi.fn();
    const { result } = renderHook(() => useLongPress(onLongPress, { delay: 450 }));

    act(() => result.current.handlers.onPointerDown(ptr(10, 10)));
    act(() => vi.advanceTimersByTime(200));
    act(() => result.current.handlers.onPointerUp(ptr(10, 10)));
    act(() => vi.advanceTimersByTime(450));

    expect(onLongPress).not.toHaveBeenCalled();
    expect(result.current.consumeLongPress()).toBe(false);
  });

  it("cancels when the pointer moves beyond the threshold (a scroll)", () => {
    const onLongPress = vi.fn();
    const { result } = renderHook(() =>
      useLongPress(onLongPress, { delay: 450, moveThreshold: 10 }),
    );

    act(() => result.current.handlers.onPointerDown(ptr(10, 10)));
    act(() => result.current.handlers.onPointerMove(ptr(40, 10))); // 30px > 10px
    act(() => vi.advanceTimersByTime(450));

    expect(onLongPress).not.toHaveBeenCalled();
  });

  it("ignores non-primary mouse buttons", () => {
    const onLongPress = vi.fn();
    const { result } = renderHook(() => useLongPress(onLongPress, { delay: 450 }));

    act(() =>
      result.current.handlers.onPointerDown(ptr(10, 10, { pointerType: "mouse", button: 2 })),
    );
    act(() => vi.advanceTimersByTime(450));

    expect(onLongPress).not.toHaveBeenCalled();
  });

  it("is inert when no handler is provided", () => {
    const { result } = renderHook(() => useLongPress(undefined, { delay: 450 }));
    act(() => result.current.handlers.onPointerDown(ptr(10, 10)));
    act(() => vi.advanceTimersByTime(450));
    expect(result.current.consumeLongPress()).toBe(false);
  });
});
