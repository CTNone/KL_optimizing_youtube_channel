# Google Flow Agent (Local)

> **Legacy / retired from the primary workflow.** The local chat bridge duplicates
> the Google Flow Agent now available on the official website and is no longer opened
> by Content Hub. Use the Flow button in Content Hub to open the website with the
> selected video's handoff folder. This source is retained for reference; it is not
> started automatically.

Local chat UI and REST bridge that reuses this repository's existing `StudioFlow` Playwright/CDP controller. It does not call an undocumented Google API or copy a Chrome login session. Chrome must already be signed in to Google Flow.

## Architecture

```text
Local browser UI (127.0.0.1:8765)
   │ REST: upload, chat, approve, state, media
   ▼
Python bridge (server.py; localhost only)
   ├── image intent ──> StudioFlow.start(...) ──> logged-in Chrome / Flow UI
   └── video intent ──> pending action card ──[approve, one-use id]──>
                        StudioFlow.start_video(...) ──> logged-in Chrome / Flow UI
   ▲                                                          │
   └──────────────────── local output files <── download ─────┘
```

The bridge binds only to loopback. The 10-credit rule is enforced by a one-use pending action on the server. The existing video controller submits exactly one video. Local keyword intent classification is intentionally dependency-free; the prompt/configuration for a future model adapter is in `agent_prompt.md`.

## Local setup (Windows)

1. Ensure the existing Flow tools' Python dependencies are installed. Use the same Python environment that runs `TOOL Video Flow\launcher.py` (Playwright, Pillow, and the project's existing dependencies).
2. Open Chrome with the Flow project already signed in. Enable Chrome's remote debugging for the running browser if needed: `chrome://inspect/#remote-debugging`, then enable **Allow remote debugging for this browser instance**. Do not copy or export the profile.
3. From the repository root run:

   ```powershell
   py "archive\TOOL Google Flow Agent\server.py"
   ```

4. Open [http://127.0.0.1:8765](http://127.0.0.1:8765), select the Chrome profile that owns the open Flow browser, then click **Kết nối Flow**. Accept Chrome's remote debugging prompt when shown.
5. Upload an image by drag-and-drop. Send a request for an image or video. Image requests start immediately. Video requests display the required 10-credit action card and only begin after **Phê duyệt**. Any image in the results gallery can be selected with **Dùng làm ảnh mẫu** for the next video request.
6. Download generated media from **Kết quả đã tải**. Files are stored under `archive\TOOL Google Flow Agent\outputs\`; uploaded references are under `uploads\`.

The UI sends `POST /api/chat`; video approval uses a separate `POST /api/approve` with the action card ID. The server consumes that ID before scheduling the controller, so replaying the approval cannot create another video. The REST endpoints are local-only; do not expose this server to a LAN or the public internet.

## Limitations

- Flow is driven through the authenticated browser UI, not a documented Google Flow API. Google UI changes can require updating the existing controller.
- The starter classifier uses Vietnamese/English keywords; specify “tạo ảnh” or “tạo video” if the intent is ambiguous. Image-to-video requires one uploaded reference image.
- The 10-credit amount is a local confirmation guardrail and does not query or reserve Google account credits.
- No real generation was run as part of implementation. Real generation uses the connected account's Flow quota.
