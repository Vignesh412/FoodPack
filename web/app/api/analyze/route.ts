import { env } from 'cloudflare:workers';
import { NextResponse } from 'next/server';

export const runtime = 'edge';

export async function POST(request: Request) {
  const apiUrl = env.FOODPROOF_API_URL;
  if (!apiUrl) {
    return NextResponse.json(
      { detail: 'The analysis service is not configured on this deployment yet.' },
      { status: 503 },
    );
  }

  const response = await fetch(`${apiUrl.replace(/\/$/, '')}/v1/analyze`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: await request.text(),
  });
  return new Response(await response.text(), {
    status: response.status,
    headers: { 'content-type': response.headers.get('content-type') ?? 'application/json' },
  });
}
