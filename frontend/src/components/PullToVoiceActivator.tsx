"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { motion, useSpring, AnimatePresence } from "framer-motion";
import { Mic, ChevronLeft } from "lucide-react";

interface PullToVoiceActivatorProps {
  onActivate: () => void;
  isActive: boolean;
}

export default function PullToVoiceActivator({ onActivate, isActive }: PullToVoiceActivatorProps) {
  const [swipeProgress, setSwipeProgress] = useState(0); // 0 to 1
  const [isDragging, setIsDragging] = useState(false);
  const startXRef = useRef<number | null>(null);
  const startYRef = useRef<number | null>(null);

  // Trackpad wheel accumulation
  const wheelAccumulatorRef = useRef<number>(0);
  const wheelTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const POINTER_THRESHOLD = 70; // Pixels for pointer drag
  const WHEEL_THRESHOLD = 180;   // Accumulated deltaX for trackpad swipe

  const springProgress = useSpring(0, { stiffness: 320, damping: 28 });

  useEffect(() => {
    springProgress.set(swipeProgress);
  }, [swipeProgress, springProgress]);

  const progressPercent = Math.round(swipeProgress * 100);

  const triggerHaptic = useCallback(() => {
    if (typeof window !== "undefined" && "vibrate" in navigator) {
      try {
        navigator.vibrate([30, 40, 30]);
      } catch (e) {
        // Ignored if browser permissions restrict haptics
      }
    }
  }, []);

  // ---------------------------------------------------------------------------
  // 1. Laptop Touchpad / Trackpad 2-Finger Horizontal Swipe (Wheel Event)
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (isActive) return;

    const handleWheel = (e: WheelEvent) => {
      // Determine horizontal scroll delta from trackpad
      let deltaX = e.deltaX;
      if (e.shiftKey && Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        deltaX = e.deltaY;
      }

      // Trackpad swipe left emits deltaX > 0
      if (deltaX > 0 && Math.abs(deltaX) > Math.abs(e.deltaY)) {
        wheelAccumulatorRef.current = Math.min(
          Math.max(wheelAccumulatorRef.current + deltaX, 0),
          WHEEL_THRESHOLD
        );

        const progress = Math.min(wheelAccumulatorRef.current / WHEEL_THRESHOLD, 1);
        setSwipeProgress(progress);
        setIsDragging(true);

        // Reset decay timer
        if (wheelTimeoutRef.current) clearTimeout(wheelTimeoutRef.current);
        wheelTimeoutRef.current = setTimeout(() => {
          wheelAccumulatorRef.current = 0;
          setSwipeProgress(0);
          setIsDragging(false);
        }, 250);

        if (progress >= 1) {
          if (wheelTimeoutRef.current) clearTimeout(wheelTimeoutRef.current);
          triggerHaptic();
          wheelAccumulatorRef.current = 0;
          setSwipeProgress(0);
          setIsDragging(false);
          onActivate();
        }
      }
    };

    window.addEventListener("wheel", handleWheel, { passive: true });
    return () => {
      window.removeEventListener("wheel", handleWheel);
      if (wheelTimeoutRef.current) clearTimeout(wheelTimeoutRef.current);
    };
  }, [isActive, onActivate, triggerHaptic]);

  // ---------------------------------------------------------------------------
  // 2. Pointer Drag / Touch Swipe Listener
  // ---------------------------------------------------------------------------
  const handlePointerDown = (e: React.PointerEvent) => {
    if (isActive) return;
    startXRef.current = e.clientX;
    startYRef.current = e.clientY;
    setIsDragging(true);
  };

  const handlePointerMove = useCallback((e: PointerEvent) => {
    if (startXRef.current === null || startYRef.current === null || isActive) return;

    const deltaX = startXRef.current - e.clientX; // Positive when dragging left
    const deltaY = Math.abs(e.clientY - startYRef.current);

    if (deltaX > 0 && deltaX > deltaY) {
      const rawProgress = Math.min(Math.max(deltaX / POINTER_THRESHOLD, 0), 1);
      setSwipeProgress(rawProgress);

      if (rawProgress >= 1) {
        triggerHaptic();
        setSwipeProgress(0);
        setIsDragging(false);
        startXRef.current = null;
        startYRef.current = null;
        onActivate();
      }
    } else if (deltaY > deltaX && swipeProgress === 0) {
      setIsDragging(false);
      startXRef.current = null;
      startYRef.current = null;
    }
  }, [isActive, onActivate, triggerHaptic, swipeProgress]);

  const handlePointerUp = useCallback(() => {
    if (startXRef.current !== null && !isActive) {
      setIsDragging(false);
      setSwipeProgress(0);
      startXRef.current = null;
      startYRef.current = null;
    }
  }, [isActive]);

  useEffect(() => {
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerUp);
    };
  }, [handlePointerMove, handlePointerUp]);

  const radius = 24;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - swipeProgress * circumference;

  return (
    <>
      {!isActive && (
        <div className="fixed top-1/2 right-0 -translate-y-1/2 z-40 flex items-center select-none pointer-events-auto">
          {/* Right Edge Interactive Pull/Swipe Tab */}
          <motion.div
            onPointerDown={handlePointerDown}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            whileHover={{ scale: 1.05, x: -4 }}
            className="flex items-center gap-2.5 px-4 py-3 rounded-l-2xl bg-zinc-900/90 border-l border-y border-zinc-800 backdrop-blur-xl shadow-2xl text-xs font-semibold text-zinc-300 hover:text-amber-400 cursor-grab active:cursor-grabbing group shadow-[0_0_25px_rgba(0,0,0,0.5)]"
          >
            <div className="relative w-6 h-6 flex items-center justify-center">
              <svg className="w-6 h-6 transform -rotate-90">
                <circle
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-zinc-800"
                  fill="transparent"
                />
                <circle
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-amber-500"
                  fill="transparent"
                  strokeDasharray={2 * Math.PI * 10}
                  strokeDashoffset={2 * Math.PI * 10 * (1 - swipeProgress)}
                  strokeLinecap="round"
                />
              </svg>
              <ChevronLeft className="w-3.5 h-3.5 text-amber-500 absolute group-hover:-translate-x-0.5 transition-transform" />
            </div>

            <span className="tracking-wide uppercase text-[11px] font-medium hidden sm:inline">
              {isDragging && swipeProgress > 0 ? `Release (${progressPercent}%)` : "Drag to Speak"}
            </span>
          </motion.div>

          {/* Active Swipe Progress Ring Overlay */}
          <AnimatePresence>
            {(isDragging || swipeProgress > 0) && (
              <motion.div
                initial={{ scale: 0.6, opacity: 0, x: 50 }}
                animate={{ scale: 1 + swipeProgress * 0.2, opacity: 1, x: -swipeProgress * 60 }}
                exit={{ scale: 0.5, opacity: 0 }}
                transition={{ type: "spring", stiffness: 350, damping: 25 }}
                className="fixed top-1/2 right-16 -translate-y-1/2 flex flex-col items-center gap-3 z-50 pointer-events-none"
              >
                <div className="relative w-20 h-20 flex items-center justify-center">
                  <div
                    className="absolute inset-0 rounded-full bg-amber-500/20 blur-xl transition-opacity"
                    style={{ opacity: swipeProgress }}
                  />

                  <svg className="w-20 h-20 transform -rotate-90">
                    <circle
                      cx="40"
                      cy="40"
                      r={radius}
                      stroke="currentColor"
                      strokeWidth="4"
                      className="text-zinc-800"
                      fill="transparent"
                    />
                    <circle
                      cx="40"
                      cy="40"
                      r={radius}
                      stroke="currentColor"
                      strokeWidth="4"
                      className="text-amber-500 transition-all duration-75"
                      fill="transparent"
                      strokeDasharray={circumference}
                      strokeDashoffset={strokeDashoffset}
                      strokeLinecap="round"
                    />
                  </svg>

                  <div className="absolute flex flex-col items-center justify-center">
                    <Mic className="w-6 h-6 text-amber-400" />
                  </div>
                </div>

                <span className="text-xs font-semibold tracking-widest text-amber-400 uppercase bg-zinc-900/90 px-3 py-1 rounded-full border border-zinc-800">
                  {progressPercent}%
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </>
  );
}
