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

  // Recording state
  const [isRecording, setIsRecording] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [clipCount, setClipCount] = useState(0);

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
        // Get current status
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
        console.log('[AIMScribe] Disconnected');
        setWsConnected(false);
        wsRef.current = null;
        // Reconnect after 3 seconds
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

    switch (message.event) {
      case 'status':
        setIsRecording(message.is_recording);
        if (message.session_id) setSessionId(message.session_id);
        break;

      case 'recording_started':
        setIsRecording(true);
        setSessionId(message.session_id);
        setRecordingDuration(0);
        setNerData(null);
        setNerVersion(0);
        setClipCount(0);
        setError(null);
        break;

      case 'recording_stopped':
        setIsRecording(false);
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
        // Handle direct response (not event)
        if (message.status === 'recording_started') {
          setIsRecording(true);
          setSessionId(message.session_id);
          setRecordingDuration(0);
          setNerData(null);
          setNerVersion(0);
          setClipCount(0);
        } else if (message.status === 'stopped') {
          setIsRecording(false);
        } else if (message.is_recording !== undefined) {
          setIsRecording(message.is_recording);
          if (message.session_id) setSessionId(message.session_id);
        }
    }
  }, [nerVersion]);

  // Connect WebSocket on mount
  useEffect(() => {
    connectWebSocket();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connectWebSocket]);

  // Update recording duration
  useEffect(() => {
    if (!isRecording) return;
    const interval = setInterval(() => {
      setRecordingDuration(prev => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [isRecording]);

  // Fallback: Poll for NER if WebSocket doesn't deliver it
  useEffect(() => {
    if (!sessionId || !isRecording) return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(`${BACKEND_API}/ner/${sessionId}`);
        const data = response.data;
        if (data.version > nerVersion && data.fields) {
          setNerData(data.fields);
          setNerVersion(data.version);
        }
      } catch (error) {
        // Session might not exist yet
      }
    }, 5000);

    return () => clearInterval(pollInterval);
  }, [sessionId, isRecording, nerVersion]);

  // Patient History button - Start/Continue recording
  const handlePatientHistory = () => {
    if (!patientData) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setError('Not connected to AIMScribe Recorder. Please wait...');
      connectWebSocket();
      return;
    }

    // Send start command via WebSocket
    // If already recording, AIMScribe will auto-stop previous and start new
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
        ner_webhook_url: `${BACKEND_API}/webhook/ner`,
      },
    };

    console.log('[AIMScribe] Starting recording for:', patientData.patient_id);
    wsRef.current.send(JSON.stringify(message));
  };

  // Stop recording manually
  const handleStopRecording = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ command: 'stop' }));
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

          {/* Recording indicator */}
          {isRecording && (
            <div className="flex items-center space-x-3 bg-red-100 px-4 py-2 rounded-lg">
              <div className="w-3 h-3 bg-red-500 rounded-full recording-pulse"></div>
              <span className="text-red-700 font-medium">
                Recording: {formatDuration(recordingDuration)}
                {clipCount > 0 && <span className="text-xs ml-2">({clipCount} clips)</span>}
              </span>
              <button
                onClick={handleStopRecording}
                className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700"
              >
                Stop
              </button>
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
                <button
                  onClick={handlePatientHistory}
                  disabled={!wsConnected}
                  className={`w-full py-3 rounded-lg font-semibold transition-colors ${
                    !wsConnected
                      ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                      : isRecording
                      ? 'bg-orange-500 text-white hover:bg-orange-600'
                      : 'bg-green-600 text-white hover:bg-green-700'
                  }`}
                >
                  {!wsConnected
                    ? 'Connecting...'
                    : isRecording
                    ? '📋 New Patient (Stops Current)'
                    : '📋 Patient History'}
                </button>
                <p className="text-xs text-gray-500 mt-2 text-center">
                  {isRecording
                    ? 'Click to stop current recording and start new'
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
