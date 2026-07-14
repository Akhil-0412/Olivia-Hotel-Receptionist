import { AccessToken } from 'livekit-server-sdk';

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const roomName = req.query.room || 'nexcell-lobby';
  const participantName = req.query.name || 'Guest';

  if (!process.env.LIVEKIT_API_KEY || !process.env.LIVEKIT_API_SECRET) {
    return res.status(500).json({ error: 'LiveKit API credentials missing' });
  }

  const at = new AccessToken(process.env.LIVEKIT_API_KEY, process.env.LIVEKIT_API_SECRET, {
    identity: participantName,
  });
  
  at.addGrant({ roomJoin: true, room: roomName });

  try {
    const token = await at.toJwt();
    res.status(200).json({
      token: token,
      url: process.env.LIVEKIT_URL
    });
  } catch (error) {
    console.error("Token generation failed:", error);
    res.status(500).json({ error: "Failed to generate token" });
  }
}
