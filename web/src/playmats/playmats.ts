// Playmat backgrounds.
//
// Official playmat ARTWORK is licensed IP and is never fetched or bundled. The
// table loads a per-player background by name; drop your own scans into
// web/public/playmats/<name>.jpg and map them here. We ship a few original,
// trademark-free CSS backdrops (starfield / hangar / nebula) as defaults.
//
// playmats.json-style mapping: leader name -> playmat key, with a fallback.

export interface Playmat {
  key: string;
  label: string;
  /** CSS background value used when no image file is supplied. */
  css: string;
  /** Optional image under /playmats/<file>; if present it wins over css. */
  file?: string;
}

export const PLAYMATS: Record<string, Playmat> = {
  starfield: {
    key: "starfield",
    label: "Deep Field",
    css:
      "radial-gradient(900px 500px at 20% 20%, rgba(70,130,200,0.20), transparent 60%)," +
      "radial-gradient(700px 600px at 85% 80%, rgba(120,80,200,0.18), transparent 60%)," +
      "linear-gradient(160deg, #0a1224 0%, #0a0f1c 55%, #070a14 100%)",
  },
  hangar: {
    key: "hangar",
    label: "Hangar Bay",
    css:
      "repeating-linear-gradient(90deg, rgba(255,160,60,0.05) 0 2px, transparent 2px 60px)," +
      "radial-gradient(800px 480px at 50% 120%, rgba(255,150,60,0.16), transparent 60%)," +
      "linear-gradient(180deg, #1a1410 0%, #12100c 60%, #0b0a08 100%)",
  },
  nebula: {
    key: "nebula",
    label: "Ion Nebula",
    css:
      "radial-gradient(700px 500px at 70% 25%, rgba(70,215,255,0.16), transparent 60%)," +
      "radial-gradient(600px 600px at 25% 85%, rgba(255,91,160,0.14), transparent 60%)," +
      "linear-gradient(150deg, #0c1422 0%, #0e0b1c 60%, #08070f 100%)",
  },
};

// Leader-name → playmat key. Falls back per seat below.
const LEADER_TO_PLAYMAT: Record<string, string> = {
  "Luke Skywalker": "starfield",
  "Darth Vader": "hangar",
};

export function playmatFor(leaderName: string | undefined, seat: "human" | "bot"): Playmat {
  if (leaderName) {
    // Leader names may carry a subtitle ("Luke Skywalker — Faithful Friend").
    const base = leaderName.split("—")[0].trim();
    const key = LEADER_TO_PLAYMAT[base];
    if (key && PLAYMATS[key]) return PLAYMATS[key];
  }
  return seat === "human" ? PLAYMATS.nebula : PLAYMATS.starfield;
}

/** CSS background for a playmat: prefer a dropped-in image, else the gradient. */
export function playmatBackground(pm: Playmat): string {
  if (pm.file) {
    return `linear-gradient(rgba(7,11,18,0.45), rgba(7,11,18,0.55)), url(/playmats/${pm.file}) center/cover`;
  }
  return pm.css;
}
