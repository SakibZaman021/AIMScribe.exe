'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import axios from 'axios';

// WebSocket for local AIMScribe.exe (works from HTTPS)
const RECORDER_WS = 'ws://localhost:5050/ws';

// Backend can be local or cloud
const BACKEND_API = process.env.NEXT_PUBLIC_BACKEND_URL
  ? `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/v1`
  : 'http://localhost:6000/api/v1';

// CMED Frontend URL for webhooks (where backend sends NER data)
const CMED_WEBHOOK_BASE = typeof window !== 'undefined'
  ? window.location.origin
  : process.env.NEXT_PUBLIC_CMED_URL || 'http://localhost:3000';

interface PatientData {
  patient_id: string;
  patient_name: string;
  age: string;
  gender: string;
  doctor_id: string;
  hospital_id: string;
  health_screening: Record<string, string>;
}

interface NERFields {
  chief_complaints?: { data: string[] };
  drug_history?: { data: string[] };
  on_examination?: { data: string[] };
  systemic_examination?: { data: string[] };
  investigations?: { data: string[] };
  diagnosis?: { data: string[] };
  medications?: { data: any[] };
  advice?: { data: string[] };
  follow_up?: { data: string[] };
  additional_notes?: { data: string[] };
}

export default function DashboardPage() {
  const router = useRouter();

  // Patient data from entry page
  const [patientData, setPatientData] = useState<PatientData | null>(null);

  // WebSocket connection
  const wsRef = useRef<WebSocket | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Recording state (synced from AIMScribe)
  const [isRecording, setIsRecording] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [recordingPatientId, setRecordingPatientId] = useState<string | null>(null);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [clipCount, setClipCount] = useState(0);
  const recordingStartTimeRef = useRef<number | null>(null);

  // NER data (received via WebSocket)
  const [nerData, setNerData] = useState<NERFields | null>(null);
  const [nerVersion, setNerVersion] = useState(0);

  // Editable fields
  const [editedFields, setEditedFields] = useState<Record<string, string>>({});

  // Error state
  const [error, setError] = useState<string | null>(null);

  // Load patient data on mount
  useEffect(() => {
    const stored = sessionStorage.getItem('patientData');
    if (stored) {
      setPatientData(JSON.parse(stored));
    } else {
      router.push('/');
    }
  }, [router]);

  // WebSocket connection
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    console.log('[AIMScribe] Connecting to', RECORDER_WS);

    try {
      const ws = new WebSocket(RECORDER_WS);

      ws.onopen = () => {
        console.log('[AIMScribe] Connected');
        setWsConnected(true);
        setError(null);
        // Get current recording status from AIMScribe (does NOT affect recording)
        ws.send(JSON.stringify({ command: 'status' }));
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          handleWsMessage(message);
        } catch (e) {
          console.error('[AIMScribe] Parse error:', e);
        }
      };

      ws.onclose = () => {
        console.log('[AIMScribe] Disconnected (recording continues in AIMScribe)');
        setWsConnected(false);
        wsRef.current = null;
        // Reconnect after 3 seconds - recording is NOT affected
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000);
      };

      ws.onerror = () => {
        setError('Cannot connect to AIMScribe Recorder. Make sure it is running.');
      };

      wsRef.current = ws;
    } catch (e) {
      setError('Failed to connect to AIMScribe Recorder');
    }
  }, []);

  // Handle WebSocket messages
  const handleWsMessage = useCallback((message: any) => {
    console.log('[AIMScribe] Received:', message.event || message.status, message);

    const event = message.event || message.status;

    switch (event) {
      case 'status':
        // Sync state from AIMScribe (page reload/reconnect)
        setIsRecording(message.is_recording || false);
        if (message.session_id) setSessionId(message.session_id);
        if (message.patient_id) setRecordingPatientId(message.patient_id);
        // Sync duration from AIMScribe
        if (message.duration_seconds) {
          setRecordingDuration(Math.floor(message.duration_seconds));
          recordingStartTimeRef.current = Date.now() - (message.duration_seconds * 1000);
        }
        break;

      case 'recording_started':
        setIsRecording(true);
        setSessionId(message.session_id);
        setRecordingPatientId(message.patient_id);
        setRecordingDuration(0);
        recordingStartTimeRef.current = Date.now();
        setNerData(null);
        setNerVersion(0);
        setClipCount(0);
        setError(null);
        break;

      case 'recording_stopped':
        setIsRecording(false);
        recordingStartTimeRef.current = null;
        break;

      case 'clip_uploaded':
        setClipCount(message.clip_number);
        break;

      case 'ner_ready':
        // Real-time NER updates via WebSocket
        if (message.version > nerVersion) {
          setNerData(message.ner);
          setNerVersion(message.version);
        }
        break;

      case 'error':
        setError(message.message || 'Recording error');
        break;

      default:
        // Handle responses with is_recording field
        if (message.is_recording !== undefined) {
          setIsRecording(message.is_recording);
          if (message.session_id) setSessionId(message.session_id);
          if (message.patient_id) setRecordingPatientId(message.patient_id);
          if (message.duration_seconds) {
            setRecordingDuration(Math.floor(message.duration_seconds));
          }
        }
    }
  }, [nerVersion]);

  // Connect WebSocket on mount
  useEffect(() => {
    connectWebSocket();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      // Don't close WebSocket on unmount - just clean up ref
      // Recording continues in AIMScribe regardless
      if (wsRef.current) wsRef.current.close();
    };
  }, [connectWebSocket]);

  // Update recording duration timer (syncs with AIMScribe start time)
  useEffect(() => {
    if (!isRecording) return;

    const interval = setInterval(() => {
      if (recordingStartTimeRef.current) {
        const elapsed = Math.floor((Date.now() - recordingStartTimeRef.current) / 1000);
        setRecordingDuration(elapsed);
      } else {
        setRecordingDuration(prev => prev + 1);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isRecording]);

  // Helper to normalize NER data format
  const normalizeNerData = (fields: any): NERFields => {
    if (!fields) return {};

    const normalize = (value: any): { data: any[] } => {
      if (!value) return { data: [] };
      if (value.data) return value; // Already in {data: [...]} format
      if (Array.isArray(value)) return { data: value };
      if (typeof value === 'object') {
        // Convert object to array of "key: value" strings
        return {
          data: Object.entries(value)
            .filter(([_, v]) => v)
            .map(([k, v]) => `${k}: ${v}`)
        };
      }
      return { data: [String(value)] };
    };

    return {
      chief_complaints: normalize(fields.chief_complaints),
      drug_history: normalize(fields.drug_history),
      on_examination: normalize(fields.on_examination),
      systemic_examination: normalize(fields.systemic_examination),
      investigations: normalize(fields.investigations),
      diagnosis: normalize(fields.diagnosis),
      medications: normalize(fields.medications),
      advice: normalize(fields.advice),
      follow_up: normalize(fields.follow_up),
      additional_notes: normalize(fields.additional_notes),
    };
  };

  // Poll for NER from backend (fallback if webhook fails)
  useEffect(() => {
    if (!sessionId || !isRecording) return;

    const pollInterval = setInterval(async () => {
      try {
        // Try backend API first
        const response = await axios.get(`${BACKEND_API}/ner/${sessionId}`);
        const data = response.data;
        if (data.version > nerVersion && data.fields) {
          setNerData(normalizeNerData(data.fields));
          setNerVersion(data.version);
        }
      } catch (error) {
        // Session might not exist yet, try CMED webhook store
        try {
          const webhookResponse = await axios.get(`/api/webhook/ner?session_id=${sessionId}`);
          const webhookData = webhookResponse.data;
          if (webhookData.version > nerVersion && webhookData.ner) {
            setNerData(webhookData.ner);
            setNerVersion(webhookData.version);
          }
        } catch {
          // Both failed, ignore
        }
      }
    }, 3000); // Poll every 3 seconds for faster updates

    return () => clearInterval(pollInterval);
  }, [sessionId, isRecording, nerVersion]);

  // Patient History button - Start recording for THIS patient
  const handlePatientHistory = () => {
    if (!patientData) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('Not connected to AIMScribe Recorder. Please wait...');
      connectWebSocket();
      return;
    }

    // Send start command via WebSocket
    // If already recording different patient, AIMScribe auto-stops previous and starts new
    const message = {
      command: 'start',
      timestamp: new Date().toISOString(),
      session: {
        patient_id: patientData.patient_id,
        patient_name: patientData.patient_name,
        doctor_id: patientData.doctor_id,
        hospital_id: patientData.hospital_id,
        age: patientData.age,
        gender: patientData.gender,
      },
      health_screening: patientData.health_screening,
      callback: {
        // Send NER webhooks to CMED frontend (this Vercel app), NOT the backend
        ner_webhook_url: `${CMED_WEBHOOK_BASE}/api/webhook/ner`,
      },
    };

    console.log('[AIMScribe] Starting recording for:', patientData.patient_id);
    wsRef.current.send(JSON.stringify(message));
  };

  // Save prescription
  const handleSavePrescription = async () => {
    if (!sessionId || !patientData) return;

    try {
      const prescription = { ...nerData, ...editedFields };
      await axios.post(`${BACKEND_API}/prescription`, {
        session_id: sessionId,
        doctor_id: patientData.doctor_id,
        prescription: prescription,
      });
      alert('Prescription saved successfully!');
    } catch (error) {
      console.error('Failed to save prescription:', error);
      alert('Failed to save prescription');
    }
  };

  // Format duration
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Render array field
  const renderArrayField = (label: string, data: string[] | undefined) => (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <textarea
        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
        rows={3}
        value={data?.join('\n') || ''}
        onChange={(e) => setEditedFields(prev => ({ ...prev, [label]: e.target.value }))}
        placeholder={`Enter ${label.toLowerCase()}...`}
      />
    </div>
  );

  if (!patientData) {
    return <div className="p-8 text-center">Loading...</div>;
  }

  // Check if recording is for current patient
  const isRecordingCurrentPatient = isRecording && recordingPatientId === patientData.patient_id;
  const isRecordingOtherPatient = isRecording && recordingPatientId && recordingPatientId !== patientData.patient_id;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <h1 className="text-2xl font-bold text-gray-800">CMED - Doctor Dashboard</h1>
            {/* Connection indicator */}
            <div className={`flex items-center space-x-1 text-sm ${wsConnected ? 'text-green-600' : 'text-red-600'}`}>
              <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <span>{wsConnected ? 'Connected' : 'Disconnected'}</span>
            </div>
          </div>

          {/* Recording indicator - NO STOP BUTTON */}
          {isRecording && (
            <div className="flex items-center space-x-3 bg-red-100 px-4 py-2 rounded-lg">
              <div className="w-3 h-3 bg-red-500 rounded-full recording-pulse"></div>
              <span className="text-red-700 font-medium">
                Recording: {formatDuration(recordingDuration)}
                {clipCount > 0 && <span className="text-xs ml-2">({clipCount} clips)</span>}
              </span>
              {recordingPatientId && (
                <span className="text-xs text-red-600">
                  Patient: {recordingPatientId}
                </span>
              )}
            </div>
          )}
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 max-w-7xl mx-auto mt-4">
          <p>{error}</p>
          <button onClick={() => setError(null)} className="text-sm underline mt-1">Dismiss</button>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Left Column - Patient Info */}
          <div className="lg:col-span-1 space-y-6">
            {/* Patient Card */}
            <div className="bg-white rounded-xl shadow p-6">
              <h2 className="text-lg font-semibold text-gray-800 mb-4">Patient Information</h2>

              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">ID:</span>
                  <span className="font-medium">{patientData.patient_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Name:</span>
                  <span className="font-medium">{patientData.patient_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Age:</span>
                  <span className="font-medium">{patientData.age || '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Gender:</span>
                  <span className="font-medium">{patientData.gender || '-'}</span>
                </div>
              </div>

              {/* Health Screening */}
              <div className="mt-6 pt-4 border-t">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Health Screening</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {patientData.health_screening.bp_systolic && (
                    <div>
                      <span className="text-gray-500">BP:</span>
                      <span className="ml-1 font-medium">
                        {patientData.health_screening.bp_systolic}/{patientData.health_screening.bp_diastolic}
                      </span>
                    </div>
                  )}
                  {patientData.health_screening.pulse_rate && (
                    <div>
                      <span className="text-gray-500">Pulse:</span>
                      <span className="ml-1 font-medium">{patientData.health_screening.pulse_rate}</span>
                    </div>
                  )}
                  {patientData.health_screening.temperature && (
                    <div>
                      <span className="text-gray-500">Temp:</span>
                      <span className="ml-1 font-medium">{patientData.health_screening.temperature}°C</span>
                    </div>
                  )}
                  {patientData.health_screening.height_cm && (
                    <div>
                      <span className="text-gray-500">Height:</span>
                      <span className="ml-1 font-medium">{patientData.health_screening.height_cm} cm</span>
                    </div>
                  )}
                  {patientData.health_screening.weight_kg && (
                    <div>
                      <span className="text-gray-500">Weight:</span>
                      <span className="ml-1 font-medium">{patientData.health_screening.weight_kg} kg</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Patient History Button - TRIGGERS RECORDING */}
              <div className="mt-6">
                {isRecordingCurrentPatient ? (
                  // Already recording this patient
                  <div className="w-full py-3 rounded-lg bg-green-100 text-green-800 font-semibold text-center">
                    Recording in Progress...
                  </div>
                ) : (
                  <button
                    onClick={handlePatientHistory}
                    disabled={!wsConnected}
                    className={`w-full py-3 rounded-lg font-semibold transition-colors ${
                      !wsConnected
                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        : isRecordingOtherPatient
                        ? 'bg-orange-500 text-white hover:bg-orange-600'
                        : 'bg-green-600 text-white hover:bg-green-700'
                    }`}
                  >
                    {!wsConnected
                      ? 'Connecting...'
                      : isRecordingOtherPatient
                      ? '📋 Start (Stops Previous Patient)'
                      : '📋 Patient History'}
                  </button>
                )}
                <p className="text-xs text-gray-500 mt-2 text-center">
                  {isRecordingCurrentPatient
                    ? 'Recording continues until next patient'
                    : isRecordingOtherPatient
                    ? 'Will stop recording for previous patient'
                    : 'Click to start recording consultation'}
                </p>
              </div>
            </div>

            {/* New Patient Button */}
            <button
              onClick={() => router.push('/')}
              className="w-full py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors"
            >
              + New Patient
            </button>
          </div>

          {/* Right Column - Prescription Fields */}
          <div className="lg:col-span-2 bg-white rounded-xl shadow p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-semibold text-gray-800">Prescription</h2>
              {nerVersion > 0 && (
                <span className="text-sm text-green-600 bg-green-100 px-3 py-1 rounded-full">
                  NER v{nerVersion}
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Left Fields */}
              <div>
                {renderArrayField('Chief Complaints', nerData?.chief_complaints?.data)}
                {renderArrayField('Drug History', nerData?.drug_history?.data)}
                {renderArrayField('On Examination', nerData?.on_examination?.data)}
                {renderArrayField('Systemic Examination', nerData?.systemic_examination?.data)}
                {renderArrayField('Investigations', nerData?.investigations?.data)}
              </div>

              {/* Right Fields */}
              <div>
                {renderArrayField('Diagnosis', nerData?.diagnosis?.data)}
                {renderArrayField('Advice', nerData?.advice?.data)}
                {renderArrayField('Follow Up', nerData?.follow_up?.data)}
                {renderArrayField('Additional Notes', nerData?.additional_notes?.data)}

                {/* Medications Table */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Medications</label>
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-2 py-1 text-left">Name</th>
                          <th className="px-2 py-1 text-left">Dose</th>
                          <th className="px-2 py-1 text-left">Freq</th>
                          <th className="px-2 py-1 text-left">Duration</th>
                        </tr>
                      </thead>
                      <tbody>
                        {nerData?.medications?.data?.map((med: any, idx: number) => (
                          <tr key={idx} className="border-t">
                            <td className="px-2 py-1">{med.name || '-'}</td>
                            <td className="px-2 py-1">{med.dose || '-'}</td>
                            <td className="px-2 py-1">{med.frequency || '-'}</td>
                            <td className="px-2 py-1">{med.duration || '-'}</td>
                          </tr>
                        )) || (
                          <tr>
                            <td colSpan={4} className="px-2 py-4 text-center text-gray-400">
                              No medications yet
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end space-x-4 mt-6 pt-4 border-t">
              <button
                onClick={handleSavePrescription}
                disabled={!sessionId}
                className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
              >
                Save Prescription
              </button>
              <button
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Print
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
// Force redeploy Thu, Apr 30, 2026  1:11:38 AM
