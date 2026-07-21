"use client";

import { useState, useCallback } from "react";
import { LiveKitRoom, RoomAudioRenderer, TrackToggle } from "@livekit/components-react";
import { Track } from "livekit-client";
import { Mic, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";

export default function OliviaWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [token, setToken] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connectToOlivia = useCallback(async () => {
    try {
      setConnecting(true);
      setError(null);
      // Generate a unique room name for this session
      const roomName = `room-${Math.random().toString(36).substring(7)}`;
      const res = await fetch(`/api/livekit?room=${roomName}&username=Guest`);
      
      if (!res.ok) {
        throw new Error("Failed to get connection token");
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

  const openWidget = () => {
    setIsOpen(true);
    connectToOlivia();
  };

  const closeWidget = () => {
    setIsOpen(false);
    setToken("");
  };

  return (
    <>
      <AnimatePresence>
        {!isOpen && (
          <motion.div 
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            className="fixed bottom-6 right-6 z-50"
          >
            <Button
              onClick={openWidget}
              size="lg"
              className="rounded-full h-16 w-16 shadow-2xl bg-amber-600 hover:bg-amber-700 text-white flex items-center justify-center transition-transform hover:scale-105"
            >
              <Mic className="h-7 w-7" />
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isOpen && (
          <motion.div 
            initial={{ opacity: 0, y: "100%" }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed inset-0 z-[100] bg-zinc-950/90 backdrop-blur-2xl flex flex-col items-center justify-center"
          >
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={closeWidget}
              className="absolute top-8 right-8 text-zinc-400 hover:text-white rounded-full h-12 w-12 hover:bg-zinc-800/50"
            >
              <X className="h-6 w-6" />
            </Button>

            <div className="text-center mb-12">
              <h2 className="text-amber-500 font-serif text-4xl md:text-5xl mb-4">Olivia</h2>
              <p className="text-zinc-400 text-lg max-w-md mx-auto">
                Your personal AI receptionist. Ask to book a room, modify a reservation, or learn about our amenities.
              </p>
            </div>

            <div className="flex flex-col items-center justify-center min-h-[200px] w-full max-w-xl">
              {error ? (
                <p className="text-red-400 text-lg">{error}</p>
              ) : connecting ? (
                <div className="flex flex-col items-center gap-4">
                  <div className="h-24 w-24 bg-zinc-900 border border-amber-500/30 rounded-full flex items-center justify-center animate-pulse">
                    <Mic className="h-8 w-8 text-amber-500/50" />
                  </div>
                  <p className="text-zinc-400 animate-pulse text-lg tracking-wide">Connecting...</p>
                </div>
              ) : token ? (
                <LiveKitRoom
                  token={token}
                  serverUrl={process.env.NEXT_PUBLIC_LIVEKIT_URL}
                  connect={true}
                  audio={true}
                  video={false}
                >
                  <div className="flex flex-col items-center gap-12 w-full">
                    <div className="relative">
                      <div className="absolute inset-0 bg-amber-500/20 rounded-full blur-2xl animate-pulse" />
                      <div className="h-32 w-32 bg-zinc-900 border border-amber-500/40 rounded-full flex items-center justify-center relative z-10 shadow-[0_0_50px_rgba(245,158,11,0.2)]">
                        <Mic className="h-10 w-10 text-amber-500" />
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-center gap-4 mt-8">
                      <TrackToggle 
                        source={Track.Source.Microphone} 
                        className="bg-zinc-800 data-[state=on]:bg-amber-600 hover:bg-zinc-700 text-white px-6 py-3 rounded-full flex items-center gap-2 border border-zinc-700 transition-all font-medium"
                      >
                        Microphone
                      </TrackToggle>
                      <Button
                        variant="destructive"
                        onClick={closeWidget}
                        className="px-6 py-3 rounded-full flex items-center gap-2 bg-red-900/50 hover:bg-red-900 text-red-100 border border-red-800"
                      >
                        <X className="h-5 w-5" /> Disconnect
                      </Button>
                    </div>
                    
                    <RoomAudioRenderer />
                  </div>
                </LiveKitRoom>
              ) : null}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
