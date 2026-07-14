export default function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Since the voice worker is always running on Hugging Face (or Render/Railway)
  // in dev mode, it automatically listens for new rooms and joins them.
  // We don't actually need to spawn a process here.
  return res.status(200).json({ 
    success: true, 
    message: 'Voice server is managed externally (Hugging Face).' 
  });
}
