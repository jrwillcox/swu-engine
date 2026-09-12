// useLongPress — a press-and-hold gesture for touch (and mouse) using the
// Pointer Events API (supported in iPad Safari). On a hold of `delay` ms with no
// movement beyond `moveThreshold` px it fires `onLongPress`, and it records that
// a long-press happened so the consumer can suppress the synthetic `click` that
// follows pointerup (a hold must inspect, not also act). Movement beyond the
// threshold cancels the timer, so dragging/scrolling a crowded arena neither
// inspects nor plays. Mouse pointers work too, so desktop behaviour is unchanged
// (hover still drives the zoom; a long mouse-press just inspects harmlessly).
import { useCallback, useRef, type PointerEvent as ReactPointerEvent } from "react";

export interface LongPressOptions {
  delay?: number;
  moveThreshold?: number;
}

export interface LongPressHandlers {
  onPointerDown: (e: ReactPointerEvent) => void;
  onPointerMove: (e: ReactPointerEvent) => void;
  onPointerUp: (e: ReactPointerEvent) => void;
  onPointerCancel: (e: ReactPointerEvent) => void;
  onPointerLeave: (e: ReactPointerEvent) => void;
}

export interface UseLongPress {
  handlers: LongPressHandlers;
  /** True if the most recent gesture fired a long-press; clears the flag.
   *  Call this at the top of an onClick to skip acting after an inspect hold. */
  consumeLongPress: () => boolean;
}

export function useLongPress(
  onLongPress: (() => void) | undefined,
  { delay = 450, moveThreshold = 10 }: LongPressOptions = {},
): UseLongPress {
  const timer = useRef<number | undefined>(undefined);
  const start = useRef<{ x: number; y: number } | null>(null);
  // A long-press fired and the trailing click should be suppressed.
  const consumed = useRef(false);

  const clearTimer = useCallback(() => {
    if (timer.current !== undefined) {
      window.clearTimeout(timer.current);
      timer.current = undefined;
    }
    start.current = null;
  }, []);

  const onPointerDown = useCallback(
    (e: ReactPointerEvent) => {
      if (!onLongPress) return;
      // Only the primary mouse button; touch/pen always count.
      if (e.pointerType === "mouse" && e.button !== 0) return;
      consumed.current = false; // fresh gesture clears any stale suppression
      clearTimer();
      start.current = { x: e.clientX, y: e.clientY };
      timer.current = window.setTimeout(() => {
        timer.current = undefined;
        consumed.current = true;
        onLongPress();
      }, delay);
    },
    [onLongPress, delay, clearTimer],
  );

  const onPointerMove = useCallback(
    (e: ReactPointerEvent) => {
      if (!start.current || timer.current === undefined) return;
      const dx = e.clientX - start.current.x;
      const dy = e.clientY - start.current.y;
      if (dx * dx + dy * dy > moveThreshold * moveThreshold) clearTimer();
    },
    [clearTimer, moveThreshold],
  );

  const onPointerUp = useCallback(() => clearTimer(), [clearTimer]);
  const onPointerCancel = useCallback(() => clearTimer(), [clearTimer]);
  const onPointerLeave = useCallback(() => clearTimer(), [clearTimer]);

  const consumeLongPress = useCallback(() => {
    const v = consumed.current;
    consumed.current = false;
    return v;
  }, []);

  return {
    handlers: { onPointerDown, onPointerMove, onPointerUp, onPointerCancel, onPointerLeave },
    consumeLongPress,
  };
}
