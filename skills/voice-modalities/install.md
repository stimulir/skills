# Install — voice-modalities

This is one of the few non-stdlib skills in the collection: the realtime
helper uses the Stimulir SDK's websocket extra and the two REST helpers use
httpx (the stimulir CLI has no voice commands to shell out to). ~5 minutes.

## 0. Prereqs

```bash
python3 --version    # 3.10+
uv sync              # installs httpx + stimulir[realtime] from pyproject.toml
```

## 1. Skill install

### Local clone + symlink

```bash
git clone https://github.com/stimulir/skills.git ~/Developer/stimulir-skills
cd ~/Developer/stimulir-skills/skills/voice-modalities && uv sync
ln -s ~/Developer/stimulir-skills/skills/voice-modalities ~/.claude/skills/voice-modalities
```

Swap `~/.claude/skills` for `~/.codex/skills` for Codex.

### `npx skills add`

```bash
npx skills add stimulir/skills
cd ~/.claude/skills/voice-modalities && uv sync
```

## 2. Credentials

```bash
export STIMULIR_API_KEY=hyb_...                       # workspace-scoped key (see connect)
export STIMULIR_API_URL=https://api.stimulir.com      # default; override for staging/self-hosted
```

The realtime helper also honors `STIMULIR_REALTIME_URL` for a full WS URL
override, and falls back to the `~/.stimulir` credentials the CLI session
wrote — so a machine that ran `connect` needs no env vars at all.

Realtime providers `gemini` / `vertex` / `openai` additionally require an
active BYOK credential for that provider on the workspace — set one up with
the `byok-register` skill. `provider=hybrie` needs no BYOK.

## 3. Verify (one bounded realtime turn)

```bash
python helpers/realtime_smoke.py --provider vertex --say "Say exactly: VOICE LANE OK"
```

Success looks like `{"session_ready": true, "audio_bytes": <nonzero>, ...}`
and exit 0. A `4403` close means the provider's BYOK credential is missing;
`4410` means the upstream rejected the session (check model id and don't
force text-only modalities on a native-audio model — see SKILL.md).

## 4. Notes

- The STT/TTS REST lanes are temporarily unavailable platform-side (see
  SKILL.md, including working realtime-as-TTS) — the helpers' request
  shapes are correct and surface the platform errors verbatim.
- No helper persists audio bytes anywhere; TTS output goes only to the
  `--out` path you name.
