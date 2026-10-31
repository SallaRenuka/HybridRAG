import { useState, useEffect, useRef, useCallback } from 'react';

// Extend window interface for Web Speech API
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

export interface UseSpeechRecognitionReturn {
  isListening: boolean;
  transcript: string;
  interimTranscript: string;
  error: string | null;
  isSupported: boolean;
  startListening: () => Promise<void>;
  stopListening: () => void;
  resetTranscript: () => void;
  clearError: () => void;
}

const getSpeechRecognitionClass = () => {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
};

export const useSpeechRecognition = (
  onResult?: (finalText: string) => void
): UseSpeechRecognitionReturn => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSupported, setIsSupported] = useState(true);

  // Store latest onResult callback in a ref to avoid tearing down recognition on re-renders
  const onResultRef = useRef(onResult);
  useEffect(() => {
    onResultRef.current = onResult;
  }, [onResult]);

  const recognitionRef = useRef<any>(null);

  // Initial browser support check
  useEffect(() => {
    const SpeechRecognitionClass = getSpeechRecognitionClass();
    if (!SpeechRecognitionClass) {
      setIsSupported(false);
    }
  }, []);

  // Cleanup active recognition session on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.onstart = null;
          recognitionRef.current.onresult = null;
          recognitionRef.current.onerror = null;
          recognitionRef.current.onend = null;
          recognitionRef.current.abort();
        } catch (_) {}
        recognitionRef.current = null;
      }
    };
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const resetTranscript = useCallback(() => {
    setTranscript('');
    setInterimTranscript('');
  }, []);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (_) {}
    }
    setIsListening(false);
  }, []);

  const startListening = useCallback(async () => {
    const SpeechRecognitionClass = getSpeechRecognitionClass();
    if (!SpeechRecognitionClass) {
      setError('Speech recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge.');
      setIsSupported(false);
      return;
    }

    setError(null);
    setInterimTranscript('');

    // 1. Explicitly verify/request microphone access via getUserMedia
    // This triggers the browser permission prompt cleanly on localhost if not yet granted
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        // Release audio track immediately so SpeechRecognition has hardware access
        stream.getTracks().forEach((track) => track.stop());
      } catch (mediaErr: any) {
        console.warn('Microphone permission check failed:', mediaErr);
        if (
          mediaErr.name === 'NotAllowedError' ||
          mediaErr.name === 'PermissionDeniedError' ||
          mediaErr.message?.includes('Permission denied')
        ) {
          setError('Microphone access denied. Please click the camera/mic icon in your browser address bar to allow microphone access.');
          setIsListening(false);
          return;
        }
        if (
          mediaErr.name === 'NotFoundError' ||
          mediaErr.name === 'DevicesNotFoundError'
        ) {
          setError('No microphone found. Please connect a microphone to use voice input.');
          setIsListening(false);
          return;
        }
      }
    }

    // 2. Abort and clean up any previous recognition instance
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onstart = null;
        recognitionRef.current.onresult = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.onend = null;
        recognitionRef.current.abort();
      } catch (_) {}
      recognitionRef.current = null;
    }

    // 3. Configure recognition instance per requirements
    try {
      const recognition = new SpeechRecognitionClass();
      recognition.lang = 'en-IN';
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsListening(true);
        setError(null);
      };

      recognition.onresult = (event: any) => {
        let interim = '';
        let finalTrans = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const res = event.results[i];
          const text = res[0]?.transcript || '';
          if (res.isFinal) {
            finalTrans += text;
          } else {
            interim += text;
          }
        }

        if (finalTrans.trim()) {
          const finalCleaned = finalTrans.trim();
          setTranscript(finalCleaned);
          if (onResultRef.current) {
            onResultRef.current(finalCleaned);
          }
        }
        setInterimTranscript(interim);
      };

      recognition.onerror = (event: any) => {
        const errorType = event.error;

        // "aborted" happens when user manually stops or cancels; do not display as an error
        if (errorType === 'aborted') {
          setIsListening(false);
          return;
        }

        let errMessage = 'Speech recognition error.';
        switch (errorType) {
          case 'not-allowed':
            errMessage = 'Microphone access denied. Please allow microphone permission in your browser address bar or settings.';
            break;
          case 'no-speech':
            errMessage = 'No speech was detected. Please click the microphone and try speaking again.';
            break;
          case 'audio-capture':
            errMessage = 'Audio capture failed. Ensure your microphone is plugged in and not in use by another application.';
            break;
          case 'network':
            errMessage = 'Network error communicating with speech recognition service. Please check your internet connection.';
            break;
          case 'service-not-allowed':
            errMessage = 'Speech recognition service is not allowed by this browser. Please try Google Chrome or Microsoft Edge.';
            break;
          case 'language-not-supported':
            errMessage = 'Language "en-IN" is not supported by your current browser settings.';
            break;
          default:
            errMessage = `Recognition error: ${errorType}`;
            break;
        }

        setError(errMessage);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
        recognitionRef.current = null;
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err: any) {
      console.error('Failed to start SpeechRecognition:', err);
      setError(`Failed to initialize speech recognition: ${err.message || 'Unknown error'}`);
      setIsListening(false);
    }
  }, []);

  return {
    isListening,
    transcript,
    interimTranscript,
    error,
    isSupported,
    startListening,
    stopListening,
    resetTranscript,
    clearError,
  };
};
