import { env } from 'cloudflare:workers';
import { NextResponse } from 'next/server';

export const runtime = 'edge';

export async function POST(request: Request) {
  const apiUrl = env.FOODPROOF_API_URL;
  if (!apiUrl) {
    return NextResponse.json(
      { detail: 'The comparison service is not configured on this deployment yet.' },
      { status: 503 },
    );
  }

  const response = await fetch(`${apiUrl.replace(/\/$/, '')}/v1/compare`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      ...(env.FOODPROOF_API_TOKEN ? { authorization: `Bearer ${env.FOODPROOF_API_TOKEN}` } : {}),
    },
    body: await request.text(),
  });
  return new Response(await response.text(), {
    status: response.status,
    headers: { 'content-type': response.headers.get('content-type') ?? 'application/json' },
  });
}
