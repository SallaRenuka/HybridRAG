import React, { useEffect } from 'react';
import { Mic, MicOff, AlertCircle, X } from 'lucide-react';
import { UseSpeechRecognitionReturn } from '../../hooks/useSpeechRecognition';

interface VoiceInputButtonProps {
  speech: UseSpeechRecognitionReturn;
  disabled?: boolean;
}

export const VoiceInputButton: React.FC<VoiceInputButtonProps> = ({
  speech,
  disabled = false,
}) => {
  const { isListening, isSupported, error, startListening, stopListening, clearError } = speech;

  // Auto-dismiss transient speech errors after 6 seconds
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => {
        clearError();
      }, 6000);
      return () => clearTimeout(timer);
    }
  }, [error, clearError]);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  if (!isSupported) {
    return (
      <div className="relative group">
        <button
          type="button"
          disabled
          aria-label="Speech recognition not supported"
          className="p-2.5 rounded-xl text-slate-400 dark:text-slate-600 cursor-not-allowed opacity-50 bg-slate-100 dark:bg-slate-900"
        >
          <MicOff className="w-5 h-5" />
        </button>
        <div className="absolute bottom-full mb-2 right-0 hidden group-hover:block z-40 px-3 py-1.5 rounded-xl bg-slate-900 text-white text-[11px] shadow-xl border border-slate-700 whitespace-nowrap">
          Voice input not supported in this browser. Use Chrome or Edge.
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex items-center">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        aria-label={isListening ? 'Stop listening' : 'Start voice input (en-IN)'}
        title={isListening ? 'Click to stop listening' : 'Click to speak question (English - India)'}
        className={`relative p-2.5 rounded-xl transition-all duration-300 flex items-center justify-center ${
          isListening
            ? 'bg-rose-500 text-white shadow-lg shadow-rose-500/30 scale-105 ring-4 ring-rose-500/25'
            : 'text-slate-500 dark:text-slate-400 hover:text-cyan-500 dark:hover:text-cyan-400 hover:bg-slate-100 dark:hover:bg-slate-800'
        }`}
      >
        {isListening ? (
          <>
            <Mic className="w-5 h-5 animate-pulse" />
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
            </span>
          </>
        ) : (
          <Mic className="w-5 h-5" />
        )}
      </button>

      {/* Floating Animated Listening Indicator & Soundwaves */}
      {isListening && (
        <div className="absolute bottom-full mb-3 right-0 sm:left-1/2 sm:-translate-x-1/2 z-40 px-4 py-2 rounded-2xl bg-slate-950/95 text-white text-xs shadow-2xl border border-rose-500/40 flex items-center gap-3 whitespace-nowrap backdrop-blur-xl animate-fade-in">
          <div className="flex items-center gap-0.5 h-3">
            <span className="w-1 bg-rose-400 rounded-full animate-waveform [animation-delay:0ms]"></span>
            <span className="w-1 bg-rose-400 rounded-full animate-waveform [animation-delay:150ms]"></span>
            <span className="w-1 bg-rose-400 rounded-full animate-waveform [animation-delay:300ms]"></span>
            <span className="w-1 bg-rose-400 rounded-full animate-waveform [animation-delay:450ms]"></span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-rose-200">Listening... Speak now</span>
            <span className="text-[10px] text-slate-400">Language: en-IN</span>
          </div>
          <button
            type="button"
            onClick={stopListening}
            className="text-[10px] uppercase font-bold text-rose-200 hover:text-white px-2 py-1 rounded-lg bg-rose-950/90 hover:bg-rose-900 border border-rose-800/80 ml-2 transition-colors"
          >
            Done
          </button>
        </div>
      )}

      {/* Meaningful Speech Error Toast with Dismiss Button */}
      {error && !isListening && (
        <div className="absolute bottom-full mb-3 right-0 sm:left-1/2 sm:-translate-x-1/2 z-40 px-3.5 py-2 rounded-xl bg-slate-900/95 dark:bg-slate-950/95 text-rose-300 border border-rose-500/40 text-xs flex items-center gap-2 shadow-2xl backdrop-blur-xl max-w-sm sm:max-w-md whitespace-normal">
          <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          <span className="flex-1 leading-snug">{error}</span>
          <button
            type="button"
            onClick={clearError}
            className="p-1 hover:bg-slate-800 rounded-md text-slate-400 hover:text-white transition-colors"
            title="Dismiss error"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};
