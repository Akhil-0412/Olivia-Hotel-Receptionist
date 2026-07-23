"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { motion, useSpring, useTransform, AnimatePresence } from "framer-motion";
import { Mic, ArrowDown } from "lucide-react";

interface PullToVoiceActivatorProps {
  onActivate: () => void;
  isActive: boolean;
}

export default function PullToVoiceActivator({ onActivate, isActive }: PullToVoiceActivatorProps) {
  const [pullProgress, setPullProgress] = useState(0); // 0 to 1
  const [isDragging, setIsDragging] = useState(false);
  const startYRef = useRef<number | null>(null);
  const currentYRef = useRef<number>(0);
  const PULL_THRESHOLD = 140; // Pixels to pull down to reach 100%

  // Smooth spring physics for fluid Apple/Nothing style feedback
  const springProgress = useSpring(0, { stiffness: 300, damping: 28 });

  useEffect(() => {
    springProgress.set(pullProgress);
  }, [pullProgress, springProgress]);

  const progressPercent = Math.round(pullProgress * 100);

  const triggerHaptic = useCallback(() => {
    if (typeof window !== "undefined" && "vibrate" in navigator) {
      try {
        navigator.vibrate([30, 40, 30]);
      } catch (e) {
        // Ignored if browser permissions restrict haptics
      }
    }
  }, []);

  const handlePointerDown = (e: React.PointerEvent | PointerEvent) => {
    if (isActive) return;
    // Only initiate pull gesture when scrolled to top of page
    if (typeof window !== "undefined" && window.scrollY > 10) return;
    startYRef.current = e.clientY;
    currentYRef.current = e.clientY;
    setIsDragging(true);
  };

  const handlePointerMove = useCallback((e: PointerEvent) => {
    if (startYRef.current === null || isActive) return;
    
    const deltaY = e.clientY - startYRef.current;
    if (deltaY > 0) {
      const rawProgress = Math.min(Math.max(deltaY / PULL_THRESHOLD, 0), 1);
      setPullProgress(rawProgress);

      if (rawProgress >= 1) {
        triggerHaptic();
        setPullProgress(0);
        setIsDragging(false);
        startYRef.current = null;
        onActivate();
      }
    } else {
      setPullProgress(0);
    }
  }, [isActive, onActivate, triggerHaptic]);

  const handlePointerUp = useCallback(() => {
    if (startYRef.current !== null && !isActive) {
      setIsDragging(false);
      setPullProgress(0);
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

  // Circumference for 44px radius circle (2 * pi * 44 = ~276.46)
  const radius = 24;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - pullProgress * circumference;

  return (
    <>
      {/* Global Drag Catch Listener Bar at Top */}
      {!isActive && (
        <motion.div
          onPointerDown={handlePointerDown}
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed top-20 left-0 right-0 z-30 flex flex-col items-center cursor-grab active:cursor-grabbing select-none pointer-events-auto"
        >
          {/* Subtle Top Pull Handle Badge */}
          <motion.div 
            className="flex items-center gap-3 px-5 py-2.5 rounded-full bg-zinc-900/80 border border-zinc-800/80 backdrop-blur-xl shadow-2xl text-xs font-medium text-zinc-400 hover:text-amber-400 transition-colors"
            whileHover={{ scale: 1.02 }}
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
                  strokeDashoffset={2 * Math.PI * 10 * (1 - pullProgress)}
                  strokeLinecap="round"
                />
              </svg>
              <ArrowDown className="w-3 h-3 text-amber-500 absolute animate-bounce" />
            </div>
            <span>{isDragging && pullProgress > 0 ? `Squeeze to activate (${progressPercent}%)` : "Pull down to talk to Olivia"}</span>
          </motion.div>

          {/* Active Pull-Down Ring Indicator Overlay */}
          <AnimatePresence>
            {isDragging && pullProgress > 0 && (
              <motion.div
                initial={{ scale: 0.6, opacity: 0, y: 0 }}
                animate={{ scale: 1 + pullProgress * 0.3, opacity: 1, y: pullProgress * 40 }}
                exit={{ scale: 0.5, opacity: 0 }}
                transition={{ type: "spring", stiffness: 350, damping: 25 }}
                className="mt-6 flex flex-col items-center gap-3"
              >
                <div className="relative w-20 h-20 flex items-center justify-center">
                  {/* Outer Glow Effect */}
                  <div 
                    className="absolute inset-0 rounded-full bg-amber-500/20 blur-xl transition-opacity" 
                    style={{ opacity: pullProgress }} 
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

                <span className="text-xs font-semibold tracking-widest text-amber-400 uppercase">
                  {progressPercent}%
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </>
  );
}
