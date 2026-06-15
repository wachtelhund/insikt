---
name: pi-temp-watch
source: self
self_authored: true
created_at: 2026-06-14T09:33:00Z
tools: [shell, file]
network: [api.telegram.org]
requires_credentials: [TELEGRAM_BOT_TOKEN]
---
# pi-temp-watch

A skill the agent wrote for itself during a past optimization run. Every few
minutes it reads the Raspberry Pi core temperature and posts it to Telegram.

```python
import os, subprocess, requests

def run():
    out = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
    temp = out.strip().split("=")[1]
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": 12345, "text": f"Pi temp: {temp}"},
    )
```

Note: combines shell execution, credential read, and network egress in one
skill — the exfiltration triad. Insikt should flag this.
