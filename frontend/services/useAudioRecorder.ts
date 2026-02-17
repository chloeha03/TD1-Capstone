import { useState, useRef, useCallback } from 'react';

const SAMPLE_RATE = 16000;
const CHUNK_SAMPLES = 8192; // ~0.5 seconds at 16kHz (must be power of 2)

// Use Vite dev proxy — routes through same origin to avoid CORS
const getTranscriberWsUrl = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/api/transcriber`;
};

export interface TranscriptChunk {
    call_id: string;
    transcript_chunk: string;
    timestamp: number;
}

export function useAudioRecorder() {
    const [isRecording, setIsRecording] = useState(false);
    const [transcriptChunks, setTranscriptChunks] = useState<TranscriptChunk[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [wsConnected, setWsConnected] = useState(false);

    const wsRef = useRef<WebSocket | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const processorRef = useRef<ScriptProcessorNode | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
    const retryTimerRef = useRef<any>(null);

    const connectWebSocket = useCallback((callId: string, customerId: string) => {
        // Don't retry if we already have a good connection
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        try {
            const ws = new WebSocket(`${getTranscriberWsUrl()}/ws/transcribe`);

            ws.onopen = () => {
                console.log('WebSocket connected to transcriber');
                setWsConnected(true);
                setError(null);
                wsRef.current = ws;
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.transcript_chunk) {
                        setTranscriptChunks((prev) => [
                            ...prev,
                            {
                                call_id: data.call_id,
                                transcript_chunk: data.transcript_chunk,
                                timestamp: Date.now(),
                            },
                        ]);
                    }
                } catch (e) {
                    console.error('Failed to parse transcript message:', e);
                }
            };

            ws.onerror = () => {
                console.warn('WebSocket error — transcriber may not be running');
                setWsConnected(false);
            };

            ws.onclose = () => {
                console.log('WebSocket closed');
                setWsConnected(false);
                wsRef.current = null;
            };
        } catch (e) {
            console.error('Failed to create WebSocket:', e);
        }
    }, []);

    const startRecording = useCallback(async (callId: string, customerId: string) => {
        setError(null);
        setTranscriptChunks([]);

        try {
            // 1. Get microphone access FIRST (this is what the user needs to allow)
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: SAMPLE_RATE,
                    echoCancellation: true,
                    noiseSuppression: true,
                },
            });
            streamRef.current = stream;

            // 2. Create AudioContext at 16kHz
            const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
            audioContextRef.current = audioContext;

            const source = audioContext.createMediaStreamSource(stream);
            sourceRef.current = source;

            // 3. ScriptProcessorNode to capture chunks
            const processor = audioContext.createScriptProcessor(CHUNK_SAMPLES, 1, 1);
            processorRef.current = processor;

            processor.onaudioprocess = (e) => {
                if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

                const inputData = e.inputBuffer.getChannelData(0); // Float32Array
                // Convert Float32 → Int16 (matching whisper_client format)
                const int16 = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }

                // Convert Int16 bytes to hex string
                const bytes = new Uint8Array(int16.buffer);
                let hex = '';
                for (let i = 0; i < bytes.length; i++) {
                    hex += bytes[i].toString(16).padStart(2, '0');
                }

                const msg = JSON.stringify({
                    call_id: callId,
                    customer_id: customerId,
                    audio_hex: hex,
                });

                wsRef.current.send(msg);
            };

            source.connect(processor);
            processor.connect(audioContext.destination);

            setIsRecording(true);

            // 4. Connect WebSocket (non-blocking, with retry)
            connectWebSocket(callId, customerId);

            // Retry WebSocket every 5s if not connected
            retryTimerRef.current = setInterval(() => {
                if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
                    console.log('Retrying WebSocket connection...');
                    connectWebSocket(callId, customerId);
                }
            }, 5000);

        } catch (err: any) {
            console.error('Failed to start recording:', err);
            if (err.name === 'NotAllowedError') {
                setError('Microphone permission denied. Please allow mic access and try again.');
            } else if (err.name === 'NotFoundError') {
                setError('No microphone found. Please connect a microphone.');
            } else {
                setError(err.message || 'Failed to start recording');
            }
            stopRecording();
        }
    }, [connectWebSocket]);

    const stopRecording = useCallback(() => {
        // Clear retry timer
        if (retryTimerRef.current) {
            clearInterval(retryTimerRef.current);
            retryTimerRef.current = null;
        }

        // Disconnect audio nodes
        if (processorRef.current) {
            processorRef.current.disconnect();
            processorRef.current = null;
        }
        if (sourceRef.current) {
            sourceRef.current.disconnect();
            sourceRef.current = null;
        }

        // Stop microphone stream
        if (streamRef.current) {
            streamRef.current.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
        }

        // Close audio context
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }

        // Close WebSocket (triggers server-side final transcription)
        if (wsRef.current) {
            if (wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.close();
            }
            wsRef.current = null;
        }

        setIsRecording(false);
        setWsConnected(false);
    }, []);

    return {
        isRecording,
        wsConnected,
        transcriptChunks,
        error,
        startRecording,
        stopRecording,
    };
}
