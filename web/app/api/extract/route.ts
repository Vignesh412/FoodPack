import { env } from 'cloudflare:workers';
import { NextResponse } from 'next/server';

export const runtime = 'edge';

export async function POST(request: Request) {
  const apiUrl = env.FOODPROOF_API_URL;
  if (!apiUrl) {
    return NextResponse.json(
      { detail: 'Photo analysis is not configured on this deployment yet. Use the demo label for now.' },
      { status: 503 },
    );
  }

  const response = await fetch(`${apiUrl.replace(/\/$/, '')}/v1/extract`, {
    method: 'POST',
    body: await request.formData(),
  });
  const body = await response.text();
  return new Response(body, {
    status: response.status,
    headers: { 'content-type': response.headers.get('content-type') ?? 'application/json' },
  });
}
