import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const passcode = body?.passcode;

  const expectedPasscode = process.env.PASSCODE;
  const authSecret = process.env.AUTH_SECRET;

  if (!expectedPasscode || !authSecret) {
    return NextResponse.json(
      { error: "Server is not configured with a passcode yet." },
      { status: 500 }
    );
  }

  if (!passcode || passcode !== expectedPasscode) {
    return NextResponse.json({ error: "Incorrect passcode." }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set("sy_session", authSecret, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30, // 30 days
  });
  return response;
}
