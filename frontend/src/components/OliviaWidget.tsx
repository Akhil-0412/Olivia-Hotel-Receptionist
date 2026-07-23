"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { LiveKitRoom, RoomAudioRenderer, TrackToggle, useRoomContext, useTranscriptions } from "@livekit/components-react";
import { Track, RoomEvent, Room } from "livekit-client";
import { Mic, MicOff, X, Volume2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";

interface OliviaWidgetProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function OliviaWidget({ isOpen, onClose }: OliviaWidgetProps) {
  const [token, setToken] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connectToOlivia = useCallback(async () => {
    try {
      setConnecting(true);
      setError(null);
      const roomName = `room-${Math.random().toString(36).substring(7)}`;
      const res = await fetch(`/api/livekit?room=${roomName}&username=Guest`);

      if (!res.ok) {
        throw new Error("Failed to connect to Olivia");
      }

      const data = await res.json();
      setToken(data.token);
    } catch (err) {
      console.error(err);
      setError("Failed to connect. Please try again later.");
    } finally {
      setConnecting(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen && !token && !connecting) {
      connectToOlivia();
    }
  }, [isOpen, token, connecting, connectToOlivia]);

  const handleClose = () => {
    setToken("");
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, scale: 0.85, backdropFilter: "blur(0px)" }}
          animate={{ opacity: 1, scale: 1, backdropFilter: "blur(32px)" }}
          exit={{ opacity: 0, scale: 0.9, backdropFilter: "blur(0px)" }}
          transition={{ type: "spring", stiffness: 260, damping: 26 }}
          className="fixed inset-0 z-[100] bg-zinc-950/95 flex flex-col items-center justify-between p-8 md:p-12 overflow-hidden select-none"
        >
          {/* Top Bar Navigation */}
          <div className="w-full max-w-4xl flex items-center justify-between z-20">
            <div className="flex items-center gap-3">
              <span className="flex h-3 w-3 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500" />
              </span>
              <span className="text-xs font-semibold tracking-widest text-zinc-300 uppercase">
                Olivia Voice Assistant
              </span>
            </div>

            <Button
              variant="ghost"
              size="icon"
              onClick={handleClose}
              className="rounded-full h-11 w-11 bg-zinc-900/80 border border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-800/80 transition-colors"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          {/* Center Voice Experience */}
          <div className="flex flex-col items-center justify-center flex-1 w-full max-w-2xl relative my-auto">
            {error ? (
              <div className="text-center space-y-4">
                <p className="text-red-400 text-lg font-medium">{error}</p>
                <Button onClick={connectToOlivia} variant="outline" className="border-zinc-700 text-zinc-200">
                  Retry Connection
                </Button>
              </div>
            ) : connecting ? (
              <div className="flex flex-col items-center gap-6">
                <div className="relative">
                  <div className="h-32 w-32 rounded-full border-2 border-amber-500/30 flex items-center justify-center animate-spin">
                    <div className="h-4 w-4 bg-amber-500 rounded-full" />
                  </div>
                </div>
                <p className="text-zinc-400 font-light text-xl tracking-wide animate-pulse">
                  Initializing Voice Channel...
                </p>
              </div>
            ) : token ? (
              <LiveKitRoom
                token={token}
                serverUrl={process.env.NEXT_PUBLIC_LIVEKIT_URL}
                connect={true}
                audio={true}
                video={false}
                className="w-full flex flex-col items-center"
              >
                <VoiceInterfaceContent onClose={handleClose} />
                <RoomAudioRenderer />
              </LiveKitRoom>
            ) : null}
          </div>

          {/* Footer Guidance */}
          <div className="z-20 text-center text-xs text-zinc-500 tracking-wider uppercase">
            Hands-free voice booking powered by Crown & Crest AI
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

{/* Active Voice Interface Content Component */}
function VoiceInterfaceContent({ onClose }: { onClose: () => void }) {
  const room = useRoomContext();
  const [audioLevel, setAudioLevel] = useState(0.3);
  const [isSpeaking, setIsSpeaking] = useState(false);

  // Live Captions state
  const [userCaption, setUserCaption] = useState("");
  const [aiCaption, setAiCaption] = useState("Hello! I'm Olivia. How may I assist your stay at Crown & Crest today?");

  // Audio level visualizer analyzer
  useEffect(() => {
    let animationFrame: number;

    const updateAudioLevel = () => {
      // Create a smooth organic pulsing waveform
      const time = Date.now() * 0.003;
      const simulatedLevel = 0.25 + Math.sin(time) * 0.15 + Math.cos(time * 1.7) * 0.1;
      setAudioLevel(simulatedLevel);
      animationFrame = requestAnimationFrame(updateAudioLevel);
    };

    updateAudioLevel();

    return () => {
      cancelAnimationFrame(animationFrame);
    };
  }, []);

  // Listen for LiveKit transcript & data events
  useEffect(() => {
    if (!room) return;

    const handleDataReceived = (payload: Uint8Array, participant?: any) => {
      try {
        const text = new TextDecoder().decode(payload);
        const data = JSON.parse(text);
        if (data.type === "transcript") {
          if (data.speaker === "user") {
            setUserCaption(data.text);
          } else {
            setAiCaption(data.text);
          }
        }
      } catch (e) {
        // Ignored if non-json
      }
    };

    room.on(RoomEvent.DataReceived, handleDataReceived);
    return () => {
      room.off(RoomEvent.DataReceived, handleDataReceived);
    };
  }, [room]);

  return (
    <div className="flex flex-col items-center gap-10 w-full">
      {/* Radial Audio Visualizer */}
      <div className="relative flex items-center justify-center w-64 h-64">
        {/* Pulsing Backlight Halo */}
        <motion.div
          animate={{ scale: [1, 1.15, 1], opacity: [0.3, 0.6, 0.3] }}
          transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
          className="absolute inset-0 rounded-full bg-gradient-to-tr from-amber-500/20 via-amber-400/10 to-amber-600/20 blur-3xl"
        />

        {/* 16 Radial Animated Frequency Bars */}
        <svg className="absolute inset-0 w-full h-full transform -rotate-90">
          {Array.from({ length: 24 }).map((_, i) => {
            const angle = (i * 360) / 24;
            const barHeight = 8 + Math.sin(Date.now() * 0.005 + i) * 12 * audioLevel;
            return (
              <line
                key={i}
                x1="128"
                y1="128"
                x2={128 + Math.cos((angle * Math.PI) / 180) * (85 + barHeight)}
                y2={128 + Math.sin((angle * Math.PI) / 180) * (85 + barHeight)}
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                className="text-amber-500/70 transition-all duration-75"
              />
            );
          })}
        </svg>

        {/* Central Core Sphere */}
        <motion.div
          animate={{ scale: 1 + audioLevel * 0.1 }}
          transition={{ type: "spring", stiffness: 300, damping: 20 }}
          className="relative z-10 w-36 h-36 rounded-full bg-zinc-900 border border-amber-500/40 flex items-center justify-center shadow-[0_0_60px_rgba(245,158,11,0.25)] backdrop-blur-xl"
        >
          <div className="flex flex-col items-center gap-1 text-amber-500">
            <Sparkles className="w-8 h-8 animate-pulse" />
            <span className="text-[10px] font-semibold tracking-widest uppercase text-amber-400/80">Listening</span>
          </div>
        </motion.div>
      </div>

      {/* Live Captions (CC) Container */}
      <div className="w-full space-y-4 text-center min-h-[120px] flex flex-col items-center justify-center">
        {/* User Speech Caption */}
        {userCaption && (
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-sm font-medium text-amber-400/90 italic bg-amber-950/40 px-4 py-2 rounded-full border border-amber-500/20 max-w-lg"
          >
            "{userCaption}"
          </motion.p>
        )}

        {/* AI Assistant Streaming Caption */}
        <motion.p
          key={aiCaption}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="text-xl md:text-2xl font-serif text-zinc-100 max-w-xl leading-relaxed font-light tracking-wide drop-shadow-md"
        >
          {aiCaption}
        </motion.p>
      </div>

      {/* Modern Controls */}
      <div className="flex items-center gap-4 mt-4 z-20">
        <TrackToggle
          source={Track.Source.Microphone}
          className="bg-zinc-900 data-[state=on]:bg-amber-500 data-[state=on]:text-zinc-950 hover:bg-zinc-800 text-zinc-200 px-6 py-3 rounded-full flex items-center gap-2 border border-zinc-800 transition-all font-medium text-sm shadow-xl"
        >
          Microphone
        </TrackToggle>

        <Button
          variant="destructive"
          onClick={onClose}
          className="px-6 py-3 rounded-full flex items-center gap-2 bg-red-950/60 hover:bg-red-900 text-red-200 border border-red-800/50 text-sm font-medium transition-all shadow-xl"
        >
          <X className="h-4 w-4" /> End Session
        </Button>
      </div>
    </div>
  );
}
