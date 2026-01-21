import React, { useMemo, useState } from "react";

/* =========================
   Greeting Dictionaries
========================= */
const GREETINGS = {
  default: [
    "👋 Hello {user}",
    "✨ Welcome back, {user}",
    "🌙 Good to see you again",
    "🚀 Ready when you are",
    "🧠 Your assistant is standing by",
  ],
  focus: [
    "🎯 Focus mode activated",
    "⚡ Let's get something done, {user}",
    "🧭 Your journey continues",
  ],
  friendly: [
    "☕ What's on your mind today, {user}?",
    "💫 Another great session awaits",
    "🌌 Let's explore together",
  ],
  minimal: ["🌟 Hello", "📌 Ready to assist"],
};

/* =========================
   Headline Dictionary
========================= */
const HEADLINES = [
  "What would you like done today?",
  "Let's continue where you left off",
  "Your next task awaits",
  "Ready to explore new possibilities?",
  "Time to get something done",
  "Your assistant is ready",
];

/* =========================
   Time-Sensitive Cute Greeting
========================= */
const getTimeGreeting = (user) => {
  const hour = new Date().getHours();

  if (hour >= 5 && hour < 9) return `🌅 Rise and shine, ${user}!`;
  if (hour >= 9 && hour < 12) return `☀️ Good morning, ${user}!`;
  if (hour >= 12 && hour < 15) return `🍽️ Lunchtime, ${user}?`;
  if (hour >= 15 && hour < 18) return `🌇 Good afternoon, ${user}!`;
  if (hour >= 18 && hour < 21) return `🌆 Evening vibes, ${user}!`;
  if (hour >= 21 && hour < 24) return `🌙 Hello night owl, ${user}! Working so late?`;
  return `💤 Burning the midnight oil, ${user}?`;
};

/* =========================
   HeaderContent Component
========================= */
const HeaderContent = ({
  username = "Labubu",
  mode = "default", // focus | friendly | minimal | default
}) => {
  const [greeting] = useState(getTimeGreeting(username)); // single greeting per load

  // Random headline
  const headline = useMemo(() => {
    return HEADLINES[Math.floor(Math.random() * HEADLINES.length)];
  }, []);

  return (
    <div className="center-content">
      <p className="greeting">{greeting}</p>
      <h1 className="headline">{headline}</h1>
    </div>
  );
};

export default HeaderContent;
