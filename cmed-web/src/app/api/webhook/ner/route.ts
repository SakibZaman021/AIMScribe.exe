/**
 * CMED Webhook Receiver - Receives NER data from AIMScribe Backend
 *
 * This endpoint receives real-time NER updates from the backend
 * and stores them for the dashboard to display.
 *
 * Updated: Fixed Map iteration for ES5 compatibility
 */

import { NextRequest, NextResponse } from 'next/server';

// CORS headers for cross-origin requests from backend
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, X-AIMScribe-Signature, X-AIMScribe-Timestamp, X-AIMScribe-Event',
};

// Handle CORS preflight
export async function OPTIONS() {
  return new NextResponse(null, { headers: corsHeaders });
}

// In-memory store for NER data (per session)
// In production, use Redis or a database
const nerStore = new Map<string, {
  ner: any;
  version: number;
  timestamp: number;
}>();

// Clean up old entries (older than 1 hour)
setInterval(() => {
  const oneHourAgo = Date.now() - 3600000;
  const keysToDelete: string[] = [];
  nerStore.forEach((value, key) => {
    if (value.timestamp < oneHourAgo) {
      keysToDelete.push(key);
    }
  });
  keysToDelete.forEach(key => nerStore.delete(key));
}, 60000);

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate webhook signature (optional security)
    const signature = request.headers.get('X-AIMScribe-Signature');
    const timestamp = request.headers.get('X-AIMScribe-Timestamp');
    const event = request.headers.get('X-AIMScribe-Event');

    console.log('[Webhook] Received:', event, body.session?.id);

    // Extract session info
    const sessionId = body.session?.id;
    if (!sessionId) {
      return NextResponse.json({ error: 'Missing session_id' }, { status: 400 });
    }

    // Store NER data
    const nerData = body.ner;
    const version = nerData?.version || 1;

    // Transform NER data to dashboard format
    const transformedNer = {
      chief_complaints: { data: nerData?.chief_complaints || [] },
      drug_history: { data: nerData?.drug_history || [] },
      on_examination: { data: formatExamination(nerData?.on_examination) },
      systemic_examination: { data: formatExamination(nerData?.systemic_examination) },
      investigations: { data: nerData?.investigations || [] },
      diagnosis: { data: nerData?.diagnosis || [] },
      medications: { data: nerData?.medications || [] },
      advice: { data: nerData?.advice || [] },
      follow_up: { data: nerData?.follow_up ? [JSON.stringify(nerData.follow_up)] : [] },
      additional_notes: { data: nerData?.additional_notes || [] },
    };

    nerStore.set(sessionId, {
      ner: transformedNer,
      version: version,
      timestamp: Date.now()
    });

    console.log('[Webhook] Stored NER v' + version + ' for session:', sessionId);

    return NextResponse.json({
      success: true,
      message: 'NER data received',
      session_id: sessionId,
      version: version
    }, { headers: corsHeaders });

  } catch (error) {
    console.error('[Webhook] Error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}

// GET endpoint for dashboard to poll
export async function GET(request: NextRequest) {
  const sessionId = request.nextUrl.searchParams.get('session_id');

  if (!sessionId) {
    return NextResponse.json({ error: 'Missing session_id' }, { status: 400 });
  }

  const data = nerStore.get(sessionId);

  if (!data) {
    return NextResponse.json({ version: 0, ner: null });
  }

  return NextResponse.json({
    version: data.version,
    ner: data.ner,
    timestamp: data.timestamp
  });
}

// Helper to format examination objects to array of strings
function formatExamination(exam: any): string[] {
  if (!exam) return [];
  if (Array.isArray(exam)) return exam;
  if (typeof exam === 'object') {
    return Object.entries(exam)
      .filter(([_, v]) => v)
      .map(([k, v]) => `${k}: ${v}`);
  }
  return [String(exam)];
}
