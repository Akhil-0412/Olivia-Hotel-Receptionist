import { AccessToken, AgentDispatchClient } from 'livekit-server-sdk';
import { NextRequest, NextResponse } from 'next/server';

export async function GET(req: NextRequest) {
  const room = req.nextUrl.searchParams.get('room');
  const username = req.nextUrl.searchParams.get('username');

  if (!room) {
    return NextResponse.json({ error: 'Missing "room" query parameter' }, { status: 400 });
  } else if (!username) {
    return NextResponse.json({ error: 'Missing "username" query parameter' }, { status: 400 });
  }

  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;
  const wsUrl = process.env.NEXT_PUBLIC_LIVEKIT_URL;

  if (!apiKey || !apiSecret || !wsUrl) {
    return NextResponse.json({ error: 'Server misconfigured' }, { status: 500 });
  }

  const at = new AccessToken(apiKey, apiSecret, { identity: username });
  at.addGrant({ roomJoin: true, room: room });

  try {
    const dispatchClient = new AgentDispatchClient(wsUrl, apiKey, apiSecret);
    await dispatchClient.createDispatch(room, "crown-crest-receptionist");
  } catch (err) {
    console.warn("Failed to dispatch agent. It may already be in the room or offline:", err);
  }

  return NextResponse.json({ token: await at.toJwt() });
}
