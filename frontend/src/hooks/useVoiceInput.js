import { useState, useEffect, useRef, useCallback } from 'react';

export default function useVoiceInput(onComplete, langCode = 'en-IN') {
  const [isListening, setIsListening] = useState(false);
  const [supportError, setSupportError] = useState(null);
  const [transcript, setTranscript] = useState('');
  const recognitionRef = useRef(null);

  useEffect(() => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      setSupportError('Voice input is not supported in this browser.');
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onstart = () => {
      setIsListening(true);
      setTranscript('');
    };

    recognition.onresult = (event) => {
      let currentTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        currentTranscript += event.results[i][0].transcript;
      }
      setTranscript(currentTranscript);
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error', event.error);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
      // We rely on the caller tracking the latest transcript state 
      // or we can pass it, but state closure might be tricky.
    };

    recognitionRef.current = recognition;

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, []);

  // Use a ref for transcript to get latest in toggle
  const transcriptRef = useRef(transcript);
  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  const toggleListening = useCallback(() => {
    if (supportError) {
      alert(supportError);
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      if (onComplete && transcriptRef.current) {
        onComplete(transcriptRef.current);
      }
      setTranscript('');
    } else {
      setTranscript('');
      recognitionRef.current.lang = langCode;
      recognitionRef.current.start();
    }
  }, [isListening, supportError, onComplete, langCode]);

  return { isListening, toggleListening, supportError, transcript };
}
