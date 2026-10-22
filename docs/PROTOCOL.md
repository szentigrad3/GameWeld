# Wand 0.0.4 local protocol

Transport:

```text
$XDG_RUNTIME_DIR/wand/wand.sock
```

Fallback when `XDG_RUNTIME_DIR` is unavailable:

```text
~/.cache/wand-runtime/wand.sock
```

Each request and response is one newline-delimited JSON object.

Examples:

```json
{"op":"providers"}
```

```json
{
  "op":"start_session",
  "app_id":1245620,
  "trainer":"/home/user/Trainers/example.exe",
  "provider":"generic-exe",
  "proton":null,
  "launch_game":true,
  "timeout_secs":120,
  "args":[]
}
```

Long-poll events:

```json
{
  "op":"watch_session",
  "id":"SESSION-UUID",
  "after":0,
  "timeout_secs":30
}
```

The server caps an individual long-poll at 60 seconds.

The socket directory is mode `0700` and the socket itself is mode `0600`.
No TCP or HTTP listener is exposed.


## Non-blocking session start

For GUI clients, prefer:

```json
{
  "op":"begin_session",
  "app_id":1245620,
  "trainer":"/home/user/Trainers/example.exe",
  "provider":"generic-exe",
  "proton":null,
  "launch_game":true,
  "timeout_secs":120,
  "args":[]
}
```

The daemon persists the session and replies immediately. Session progression
continues in a daemon task. Read the session by UUID or use `watch_session`.

`start_session` remains available for CLI/backward compatibility and waits until
the session reaches Running, Stopped, or Failed.


## Daemon status

```json
{"op":"status"}
```

Returns the daemon version, discovered Steam root, installed-game count,
provider count and persisted-session count. Native clients use this for
connection/reconnection state.


## 0.0.7 provider/runtime inspection

Provider health:

```json
{"op":"provider_health","provider":null}
```

Process probe:

```json
{"op":"processes","app_id":1245620}
```

Preferences:

```json
{"op":"preferences"}
```

```json
{
  "op":"set_preferences",
  "preferences":{
    "onboarding_complete":true,
    "default_provider":"generic-exe",
    "launch_game_automatically":true,
    "diagnostics_directory":null
  }
}
```

Structured log tail:

```json
{"op":"logs","lines":200}
```
