# Voice: dictation, hands-free mode, and a local voice

Status: built, off by default. Turned on by setting `SPEECH_URL` on the server.

## What it is
- **Dictation.** A microphone button in the composer. Tap, ask, the words appear in the box. It ends when you stop talking or tap again.
- **Hands-free.** The waveform button (shown when the box is empty) opens a full-screen conversation: ask aloud, hear the short answer, ask the next. Tap the big button to interrupt the voice or finish a question early.
- **Local voice.** The server speaks through the shared speech host (open models) before Fish/ElevenLabs/Kokoro. Spoken answers use the same chain and cache as the map tour.

## Where the models run
The shared speech host (`chatbots` repo, `speech/server.py`) on the MacBook Pro, reached from the VPS through the existing tunnel at `127.0.0.1:18799`. This app never loads models. It does **not** pass a `stack` unless `SPEECH_STACK` is set, because the host is shared and swapping stacks unloads another tool's models.

## Server
- `app/speech.py`: client (`status`, `stt`, `tts`, `warm`). Audio is never written to disk; TTS PCM is wrapped as WAV.
- `POST /api/stt`: WAV in. The speech host first; ElevenLabs only when keyed and the host fails or is off. 413 over 2 MB, 415 for non-WAV when only the host is available, 429 on the hourly cap (`SPEECH_STT_PER_HOUR`, default 600), 503 with a `reason` otherwise.
- TTS chain: `speech` first. Clips cache as `.wav`; endpoints label the media type by sniffing `RIFF`. `/api/tts_ts` adds `format`.
- `POST /api/speech/warm`, and `speech` in `/api/health`.
- Env: `SPEECH_URL`, `SPEECH_DISABLE`, `SPEECH_STACK`, `SPEECH_VOICE`, `SPEECH_STT_TIMEOUT_S`, `SPEECH_TTS_TIMEOUT_S`, `TTS_DISABLE_SPEECH`.

## Browser
- `lib/audio.ts` (pure, unit tested): downmix, resample to 16 kHz, WAV encode, noise-floor endpointing.
- `lib/mic.ts`: capture one utterance; releases the microphone immediately.
- `lib/speech.ts`: availability from `/api/health`, warm, transcribe.
- `hooks/use-dictation.ts`, `components/VoiceMode.tsx`, narrator `server` option (local voice first, browser voice if it fails).
- The buttons appear only when `/api/health` says the server can transcribe.

## Measured (Phase 0, synthetic macOS voices, 60 clips)
STT word error 0.2% (legal terms 65/66), server p50 147 ms / p95 197 ms, first call after idle 6.2 s wall; TTS first audio p50 165 ms, whole line about 0.8 s. 10 concurrent requests all succeeded (queued). The host's active stack changed on its own during the run (multilingual to english-fast, 5.8 s swap), so another client shares it; that is why we never request a stack by default. Real speech is not yet measured; synthetic voices flatter the numbers.

## Validation
- `tests/test_speech.py`: fake host speaking the real contract; fallbacks, caps, limits, cache, media types, health, no audio written.
- `web/src/lib/audio.test.ts` (`pnpm test`).
- Browser run with a synthetic microphone: dictation filled the box; hands-free looped listen, hear, transcribe, ask, speak, listen.
- Not yet verified: real microphones on iOS Safari and Android Chrome, echo (the voice heard by the mic) on speakers, real accents, and the host sleeping.

## Rollout
1. Merge. Nothing changes without `SPEECH_URL`.
2. On the VPS set `SPEECH_URL=http://127.0.0.1:18799` (the tunnel the copilot already uses) and redeploy. Check `/api/health` shows `speech.ok`.
3. Roll back by unsetting `SPEECH_URL` (or `SPEECH_DISABLE=1`); buttons disappear and the old chain returns.
4. Record about 20 real clips on a phone for a true word-error number.
