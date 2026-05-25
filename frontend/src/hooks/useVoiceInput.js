import { useState, useRef, useCallback } from 'react';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'https://cliniq-ai-kqfz.onrender.com';

// Language code → Whisper language hint mapping
const LANG_TO_WHISPER = {
  'en-IN': 'en',
  'hi-IN': 'hi',
  'ta-IN': 'ta',
  'te-IN': 'te',
  'bn-IN': 'bn',
  'mr-IN': 'mr',
};

/**
 * useVoiceInput — records audio via MediaRecorder and transcribes using
 * Groq Whisper (via backend /api/analyze/transcribe).
 *
 * Falls back to browser SpeechRecognition if MediaRecorder is unavailable.
 *
 * Returns:
 *   isListening    — true while recording
 *   isTranscribing — true while waiting for Groq to return the transcript
 *   toggleListening — start/stop recording
 *   transcript     — live interim text (empty with Whisper until done)
 *   error          — any mic/transcription error string
 */
export default function useVoiceInput(onComplete, langCode = 'en-IN') {
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState(null);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);

  // ── Groq Whisper path ──────────────────────────────────────────────────────

  const startWhisper = useCallback(async () => {
    setError(null);
    setTranscript('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Prefer webm (Chrome/Edge), fall back to ogg (Firefox)
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/ogg;codecs=opus';

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        // Stop all tracks to release microphone
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;

        const blob = new Blob(chunksRef.current, { type: mimeType });
        chunksRef.current = [];

        if (blob.size < 1000) {
          // Too small — probably nothing was said
          setIsTranscribing(false);
          return;
        }

        setIsTranscribing(true);

        try {
          const ext = mimeType.includes('ogg') ? 'ogg' : 'webm';
          const filename = `recording.${ext}`;
          const formData = new FormData();
          formData.append('file', blob, filename);

          // Optionally hint the language to Whisper
          const whisperLang = LANG_TO_WHISPER[langCode];
          if (whisperLang && whisperLang !== 'en') {
            formData.append('language', whisperLang);
          }

          const res = await axios.post(
            `${API_URL}/api/analyze/transcribe`,
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' } }
          );

          const text = res.data?.data?.text?.trim();
          if (text && onComplete) {
            setTranscript(text);
            onComplete(text);
          }
        } catch (err) {
          console.error('Whisper transcription failed:', err);
          setError('Transcription failed — check backend connection.');
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.start(250); // collect chunks every 250ms
      setIsListening(true);
    } catch (err) {
      console.error('Microphone access error:', err);
      if (err.name === 'NotAllowedError') {
        setError('Microphone access denied. Please allow microphone in browser settings.');
      } else if (err.name === 'NotFoundError') {
        setError('No microphone found. Please connect a microphone.');
      } else {
        setError('Could not access microphone: ' + err.message);
      }
    }
  }, [langCode, onComplete]);

  const stopWhisper = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop(); // triggers onstop → transcription
    }
    setIsListening(false);
  }, []);

  // ── Toggle ─────────────────────────────────────────────────────────────────

  const toggleListening = useCallback(() => {
    if (isTranscribing) return; // don't allow re-trigger while transcribing

    if (isListening) {
      stopWhisper();
    } else {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError('Your browser does not support audio recording.');
        return;
      }
      startWhisper();
    }
  }, [isListening, isTranscribing, startWhisper, stopWhisper]);

  return {
    isListening,
    isTranscribing,
    toggleListening,
    transcript,
    error,
    // Legacy alias for modules that use supportError
    supportError: error,
  };
}
