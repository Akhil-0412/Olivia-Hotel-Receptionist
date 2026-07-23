"use client";

import { useState } from "react";
import Image from "next/image";
import { motion, useScroll, useTransform } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import OliviaWidget from "@/components/OliviaWidget";
import PullToVoiceActivator from "@/components/PullToVoiceActivator";
import { Button } from "@/components/ui/button";
import { MapPin, Star, Clock, Wifi, Calendar, User } from "lucide-react";
import Link from "next/link";

const rooms = [
  {
    name: "Standard Twin",
    desc: "Perfect for friends or colleagues travelling together.",
    price: "from £95",
    img: "/images/room-twin.png",
  },
  {
    name: "Deluxe Double",
    desc: "Experience ultimate comfort in our signature double room.",
    price: "from £155",
    img: "/images/room-king.png",
  },
  {
    name: "Executive Suite",
    desc: "Spacious luxury with panoramic city views.",
    price: "from £290",
    img: "/images/room-executive.png",
  },
];

export default function Home() {
  const [isVoiceActive, setIsVoiceActive] = useState(false);
  const { scrollYProgress } = useScroll();
  const scaleY = useTransform(scrollYProgress, [0, 1], [0, 1]);

  return (
    <main className="bg-zinc-950 min-h-screen text-zinc-50 overflow-hidden font-sans selection:bg-amber-500/30">
      
      {/* Scroll Progress Line */}
      <motion.div 
        className="fixed top-0 left-0 w-1 h-screen bg-gradient-to-b from-amber-400 to-amber-600 z-[100] origin-top drop-shadow-[0_0_8px_rgba(245,158,11,0.8)]"
        style={{ scaleY }}
      />

      {/* Navigation */}
      <nav className="fixed top-0 w-full z-40 bg-zinc-950/80 backdrop-blur-md border-b border-zinc-800/50">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-3"
          >
            <div className="relative w-10 h-10 rounded-full overflow-hidden border border-amber-500/40 shadow-[0_0_15px_rgba(245,158,11,0.25)]">
              <Image 
                src="/images/logo.png" 
                alt="Crown & Crest Logo" 
                fill 
                className="object-cover" 
              />
            </div>
            <span className="font-serif text-xl tracking-widest text-amber-500 uppercase font-light">Crown & Crest</span>
          </motion.div>
          
          <motion.div 
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="hidden md:flex gap-8 text-sm font-medium tracking-wide text-zinc-300 items-center"
          >
            <a href="#about" className="hover:text-amber-500 transition-colors">Experience</a>
            <a href="#rooms" className="hover:text-amber-500 transition-colors">Rooms</a>
            <a href="#dining" className="hover:text-amber-500 transition-colors">Dining</a>
            <Link href="/guest" className="flex items-center gap-2 text-amber-500 hover:text-amber-400 transition-colors border border-amber-500/50 px-4 py-2 rounded-full">
              <User className="w-4 h-4" /> Guest Portal
            </Link>
          </motion.div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative h-screen flex items-center justify-center">
        {/* Background Image with Parallax effect */}
        <motion.div 
          className="absolute inset-0 z-0"
          initial={{ scale: 1.1, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 1.5, ease: "easeOut" }}
        >
          <Image
            src="/images/hero-exterior.png"
            alt="Crown & Crest Exterior"
            fill
            className="object-cover opacity-40 mix-blend-luminosity"
            priority
          />
          <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/60 to-transparent" />
        </motion.div>

        <div className="relative z-10 max-w-4xl mx-auto px-6 text-center mt-20">
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-amber-500 uppercase tracking-[0.3em] text-sm md:text-base font-semibold mb-6"
          >
            Welcome to Unparalleled Luxury
          </motion.p>
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="text-5xl md:text-7xl lg:text-8xl font-serif mb-8 text-zinc-100 leading-tight"
          >
            Experience the <br className="hidden md:block"/> Art of Hospitality
          </motion.h1>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
            className="flex flex-col sm:flex-row gap-4 justify-center items-center"
          >
            {/* The primary CTA is Olivia (Widget handles its own button, but we can trigger it or add a manual booking button here) */}
            <Link href="/book">
              <Button className="bg-amber-500 hover:bg-amber-400 text-zinc-950 px-8 py-6 rounded-full text-lg tracking-wide uppercase font-semibold transition-all duration-300 flex items-center gap-2 shadow-[0_0_25px_rgba(245,158,11,0.3)] hover:scale-105">
                <Calendar className="w-5 h-5" /> Book Now
              </Button>
            </Link>
            <p className="text-zinc-400 italic text-sm mt-4 sm:mt-0 sm:absolute sm:-bottom-12 flex items-center justify-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-amber-500 animate-ping" />
              Pull down anywhere on screen to speak with Olivia
            </p>
          </motion.div>
        </div>
      </section>

      {/* About / Experience */}
      <section id="about" className="py-32 bg-zinc-950 relative">
        <div className="max-w-7xl mx-auto px-6 grid md:grid-cols-2 gap-16 items-center">
          <motion.div 
            initial={{ opacity: 0, x: -50 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            className="space-y-6"
          >
            <h2 className="text-4xl md:text-5xl font-serif text-zinc-100">Where Heritage Meets Modern Luxury</h2>
            <p className="text-zinc-400 text-lg leading-relaxed">
              Nestled in the heart of the city, Crown & Crest offers a sanctuary of refined elegance. From our meticulously curated lounges to our world-class concierge service, every detail is designed to elevate your stay.
            </p>
            <p className="text-zinc-400 text-lg leading-relaxed">
              Whether you are travelling for business or leisure, experience a seamless blend of historic charm and cutting-edge amenities.
            </p>
          </motion.div>
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, margin: "-100px" }}
            className="relative h-[600px] w-full rounded-2xl overflow-hidden"
          >
            <Image 
              src="/images/about-lounge.png"
              alt="Luxury Lounge"
              fill
              className="object-cover"
            />
          </motion.div>
        </div>
      </section>

      {/* Room Showcase */}
      <section id="rooms" className="py-32 bg-zinc-900 relative">
        <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-[0.03] mix-blend-overlay" />
        <div className="max-w-7xl mx-auto px-6 relative z-10">
          <div className="text-center mb-20">
            <h2 className="text-4xl md:text-5xl font-serif text-zinc-100 mb-4">Our Accommodations</h2>
            <p className="text-zinc-400 max-w-2xl mx-auto text-lg">
              Designed with meticulous attention to detail, our rooms offer a sanctuary of comfort and style.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {rooms.map((room, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ delay: i * 0.2 }}
                whileHover={{ y: -10 }}
              >
                <Card className="bg-zinc-950 border-zinc-800 overflow-hidden group h-full flex flex-col">
                  <div className="relative h-64 overflow-hidden">
                    <div className="absolute inset-0 bg-black/20 group-hover:bg-transparent transition-colors z-10" />
                    <Image
                      src={room.img}
                      alt={room.name}
                      fill
                      className="object-cover transform group-hover:scale-110 transition-transform duration-700"
                    />
                  </div>
                  <CardContent className="p-8 flex-1 flex flex-col">
                    <div className="flex justify-between items-start mb-4">
                      <h3 className="text-2xl font-serif text-zinc-100">{room.name}</h3>
                      <span className="text-amber-500 font-medium">{room.price}<span className="text-sm text-zinc-500 font-normal">/night</span></span>
                    </div>
                    <p className="text-zinc-400 mb-6 flex-1">{room.desc}</p>
                    <Link href={`/book?room=${room.name.toLowerCase().replace(" ", "_")}`}>
                      <Button variant="outline" className="w-full border-amber-500/50 text-amber-500 hover:bg-amber-500 hover:text-zinc-950 transition-colors">
                        Book Now
                      </Button>
                    </Link>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Culinary & Wellness (Side by Side or Stacked) */}
      <section id="dining" className="py-32 bg-zinc-950">
        <div className="max-w-7xl mx-auto px-6 grid md:grid-cols-2 gap-8">
          
          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            className="group relative h-[500px] overflow-hidden rounded-2xl"
          >
            <Image src="/images/dining-restaurant.png" alt="Dining" fill className="object-cover transition-transform duration-700 group-hover:scale-105" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" />
            <div className="absolute bottom-0 left-0 p-10">
              <h3 className="text-3xl font-serif text-amber-500 mb-3">Culinary Excellence</h3>
              <p className="text-zinc-300">Savour world-class gastronomy in an intimate, moody setting.</p>
            </div>
          </motion.div>

          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ delay: 0.2 }}
            className="group relative h-[500px] overflow-hidden rounded-2xl"
          >
            <Image src="/images/spa-pool.png" alt="Spa and Wellness" fill className="object-cover transition-transform duration-700 group-hover:scale-105" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" />
            <div className="absolute bottom-0 left-0 p-10">
              <h3 className="text-3xl font-serif text-amber-500 mb-3">Spa & Wellness</h3>
              <p className="text-zinc-300">Rejuvenate your senses in our tranquil indoor pool and therapy rooms.</p>
            </div>
          </motion.div>

        </div>
      </section>

      {/* Features */}
      <section className="py-20 bg-zinc-900 border-t border-zinc-800">
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8">
          {[
            { icon: Star, title: "5-Star Service", desc: "Award-winning hospitality" },
            { icon: MapPin, title: "Prime Location", desc: "Heart of the city center" },
            { icon: Clock, title: "24/7 Concierge", desc: "Always at your service" },
            { icon: Wifi, title: "High-Speed Wi-Fi", desc: "Complimentary in all areas" },
          ].map((feature, i) => (
            <motion.div 
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ delay: i * 0.1 }}
              className="flex flex-col items-center text-center p-6 rounded-2xl bg-zinc-950/50 border border-zinc-800/50"
            >
              <feature.icon className="h-10 w-10 text-amber-500 mb-4" strokeWidth={1.5} />
              <h3 className="text-lg font-medium text-zinc-200 mb-2">{feature.title}</h3>
              <p className="text-sm text-zinc-400">{feature.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-zinc-950 py-12 border-t border-zinc-900 text-center">
        <div className="max-w-7xl mx-auto px-6">
          <p className="text-zinc-500 text-sm">
            © {new Date().getFullYear()} Crown & Crest Hotel. All rights reserved.
          </p>
        </div>
      </footer>

      {/* Pull Down Gesture Activator */}
      <PullToVoiceActivator 
        onActivate={() => setIsVoiceActive(true)} 
        isActive={isVoiceActive} 
      />

      {/* LiveKit Morphing Voice Interface */}
      <OliviaWidget 
        isOpen={isVoiceActive} 
        onClose={() => setIsVoiceActive(false)} 
      />

    </main>
  );
}
