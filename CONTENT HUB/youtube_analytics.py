"""Read-only YouTube Analytics/OAuth client with one token per channel."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import secrets
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from store import DomainError, youtube_video_id

SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
API_ROOT = "https://youtubeanalytics.googleapis.com/v2/reports"


def app_data_dir():
    base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    return base / "YouTubeContentHub"


def video_id_from_url(value):
    return youtube_video_id(value)


class YouTubeAnalyticsClient:
    def __init__(self):
        self.folder = app_data_dir()
        self.client_path = self.folder / "youtube_oauth_client.json"
        self.tokens_dir = self.folder / "tokens"

    def _channel_id(self, channel_id):
        channel_id = str(channel_id or "").strip()
        if not channel_id:
            raise DomainError("Chọn kênh có YouTube channel ID trước.")
        return channel_id

    def _token_path(self, channel_id):
        safe = "".join(ch for ch in self._channel_id(channel_id) if ch.isalnum() or ch in "-_")
        return self.tokens_dir / f"{safe}.json"

    def token_path_for(self, channel_id):
        return self._token_path(channel_id)

    def _reach_path(self, channel_id):
        return self.tokens_dir / f"{self._token_path(channel_id).stem}_reach_job.json"

    def configure(self, source):
        source = Path(source)
        try:
            content = json.loads(source.read_text(encoding="utf-8-sig"))
            client = content.get("installed")
            if not client or not client.get("client_id") or not client.get("client_secret"):
                raise ValueError("Chỉ hỗ trợ OAuth client loại Desktop app (installed).")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise DomainError(f"Không đọc được OAuth client JSON: {error}") from error
        self.folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, self.client_path)

    def _client(self):
        if not self.client_path.is_file():
            raise DomainError("Chưa cấu hình OAuth. Bấm Kết nối Google và chọn file JSON OAuth Desktop app.")
        try:
            data = json.loads(self.client_path.read_text(encoding="utf-8"))
            client = data["installed"]
            return {key: client[key] for key in ("client_id", "client_secret", "auth_uri", "token_uri")}
        except (OSError, ValueError, KeyError) as error:
            raise DomainError("File OAuth Desktop app không hợp lệ. Hãy chọn lại file JSON từ Google Cloud.") from error

    def _save_token(self, token, channel_id):
        path = self._token_path(channel_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(token, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    def _post_form(self, url, fields):
        request = urllib.request.Request(
            url, data=urllib.parse.urlencode(fields).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try:
                details = json.loads(error.read().decode("utf-8"))
                reason = details.get("error_description") or details.get("error", "")
            except (ValueError, OSError):
                reason = ""
            raise DomainError(f"Google OAuth trả lời {error.code}. {reason}".strip()) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise DomainError(f"Không kết nối được Google: {error}") from error

    def connect(self, channel_id):
        channel_id = self._channel_id(channel_id)
        client = self._client()
        state = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
        callback = {"event": threading.Event(), "code": "", "error": ""}

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(handler):
                query = urllib.parse.parse_qs(urllib.parse.urlparse(handler.path).query)
                if query.get("state", [""])[0] != state:
                    callback["error"] = "Phản hồi đăng nhập không hợp lệ (state không khớp)."
                elif query.get("error"):
                    callback["error"] = query["error"][0]
                else:
                    callback["code"] = query.get("code", [""])[0]
                body = ("Đã kết nối Google. Bạn có thể đóng cửa sổ này và quay lại Content Hub."
                        if callback["code"] else "Không hoàn tất kết nối. Hãy quay lại Content Hub.")
                payload = body.encode("utf-8")
                handler.send_response(200)
                handler.send_header("Content-Type", "text/html; charset=utf-8")
                handler.send_header("Content-Length", str(len(payload)))
                handler.end_headers()
                handler.wfile.write(payload)
                callback["event"].set()

            def log_message(self, *_args):
                return

        try:
            server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
        except OSError as error:
            raise DomainError(f"Không thể mở cổng nhận phản hồi OAuth: {error}") from error
        server.timeout = 1
        redirect_uri = f"http://127.0.0.1:{server.server_port}/"
        parameters = {"client_id": client["client_id"], "redirect_uri": redirect_uri,
                      "response_type": "code", "scope": SCOPE, "access_type": "offline",
                      "prompt": "consent", "state": state, "code_challenge": challenge,
                      "code_challenge_method": "S256"}
        webbrowser.open(client["auth_uri"] + "?" + urllib.parse.urlencode(parameters))
        try:
            deadline = time.monotonic() + 240
            while not callback["event"].is_set() and time.monotonic() < deadline:
                server.handle_request()
            if not callback["event"].is_set():
                raise DomainError("Hết thời gian chờ đăng nhập Google. Bấm kết nối và thử lại.")
        finally:
            server.server_close()
        if callback["error"]:
            raise DomainError(f"Đăng nhập Google không hoàn tất: {callback['error']}")
        token = self._post_form(client["token_uri"], {
            "client_id": client["client_id"], "client_secret": client["client_secret"],
            "code": callback["code"], "grant_type": "authorization_code",
            "redirect_uri": redirect_uri, "code_verifier": verifier})
        token["expires_at"] = time.time() + int(token.get("expires_in", 3600))
        self._save_token(token, channel_id)

    def disconnect(self, channel_id):
        path = self._token_path(channel_id)
        try:
            token = json.loads(path.read_text(encoding="utf-8"))
            grant = token.get("refresh_token") or token.get("access_token")
            if grant:
                request = urllib.request.Request(
                    "https://oauth2.googleapis.com/revoke",
                    data=urllib.parse.urlencode({"token": grant}).encode("utf-8"),
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
                try:
                    with urllib.request.urlopen(request, timeout=20):
                        pass
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
                    pass
        except (OSError, ValueError):
            pass
        for file in (path, self._reach_path(channel_id)):
            try:
                file.unlink()
            except FileNotFoundError:
                pass

    def _access_token(self, channel_id):
        channel_id = self._channel_id(channel_id)
        client = self._client()
        path = self._token_path(channel_id)
        try:
            token = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.connect(channel_id)
            token = json.loads(path.read_text(encoding="utf-8"))
        if token.get("access_token") and float(token.get("expires_at", 0)) > time.time() + 60:
            return token["access_token"]
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            self.connect(channel_id)
            token = json.loads(path.read_text(encoding="utf-8"))
            refresh_token = token.get("refresh_token")
        if not refresh_token:
            raise DomainError("Token Google không có refresh token. Hãy kết nối lại kênh này.")
        renewed = self._post_form(client["token_uri"], {
            "client_id": client["client_id"], "client_secret": client["client_secret"],
            "refresh_token": refresh_token, "grant_type": "refresh_token"})
        token.update(renewed)
        token["expires_at"] = time.time() + int(renewed.get("expires_in", 3600))
        self._save_token(token, channel_id)
        return token["access_token"]

    def _query(self, parameters, channel_id):
        token = self._access_token(channel_id)
        url = API_ROOT + "?" + urllib.parse.urlencode(parameters)
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try:
                details = json.loads(error.read().decode("utf-8"))
                reason = details.get("error", {}).get("message", "")
            except (ValueError, OSError):
                reason = ""
            raise DomainError(f"YouTube Analytics API trả lời {error.code}. {reason}".strip()) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise DomainError(f"Không kết nối được YouTube Analytics API: {error}") from error

    def _reporting_request(self, path, parameters=None, body=None, channel_id=""):
        token = self._access_token(channel_id)
        url = "https://youtubereporting.googleapis.com/v1/" + path
        if parameters:
            url += "?" + urllib.parse.urlencode(parameters)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Authorization": f"Bearer {token}"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try:
                details = json.loads(error.read().decode("utf-8"))
                reason = details.get("error", {}).get("message", "")
            except (ValueError, OSError):
                reason = ""
            raise DomainError(f"YouTube Reporting API trả lời {error.code}. {reason}".strip()) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise DomainError(f"Không kết nối được YouTube Reporting API: {error}") from error

    def _download_report(self, url, channel_id):
        token = self._access_token(channel_id)
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8-sig")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            raise DomainError(f"Không tải được báo cáo CTR: {error}") from error

    def _reach_job_id(self, channel_id):
        job_file = self._reach_path(channel_id)
        job_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            job = json.loads(job_file.read_text(encoding="utf-8"))
            if job.get("id"):
                return job["id"]
        except (OSError, ValueError):
            pass
        jobs = self._reporting_request("jobs", {"pageSize": 50}, channel_id=channel_id)
        job = next((item for item in jobs.get("jobs", [])
                    if item.get("reportTypeId") == "channel_reach_basic_a1"), None)
        if not job:
            job = self._reporting_request("jobs", body={
                "reportTypeId": "channel_reach_basic_a1", "name": "Content Hub video reach"},
                channel_id=channel_id)
        job_file.write_text(json.dumps({"id": job["id"]}, indent=2), encoding="utf-8")
        try:
            os.chmod(job_file, 0o600)
        except OSError:
            pass
        return job["id"]

    def _reach_rows(self, channel_id):
        job_id = self._reach_job_id(channel_id)
        cutoff = date.today() - timedelta(days=28)
        cutoff_time = datetime(cutoff.year, cutoff.month, cutoff.day, tzinfo=timezone.utc)
        parameters = {"pageSize": 100,
                      "startTimeAtOrAfter": cutoff_time.isoformat().replace("+00:00", "Z")}
        reports = []
        while True:
            page = self._reporting_request(
                f"jobs/{urllib.parse.quote(job_id, safe='')}/reports", parameters,
                channel_id=channel_id)
            reports.extend(page.get("reports", []))
            if not page.get("nextPageToken"):
                break
            parameters["pageToken"] = page["nextPageToken"]
        rows = []
        for report in reports:
            start = report.get("startTime", "")
            if not start:
                continue
            report_day = datetime.fromisoformat(start.replace("Z", "+00:00")).date()
            if report_day < cutoff:
                continue
            for row in csv.DictReader(io.StringIO(self._download_report(report["downloadUrl"], channel_id))):
                try:
                    impressions = float(row.get("video_thumbnail_impressions", 0) or 0)
                    ctr_percent = float(row.get("video_thumbnail_impressions_ctr", 0) or 0)
                except ValueError:
                    continue
                rows.append({"date": report_day, "video_id": row.get("video_id", ""),
                             "impressions": impressions, "ctr_percent": ctr_percent})
        return rows

    @staticmethod
    def _reach_summary(rows):
        impressions = sum(row["impressions"] for row in rows)
        if not rows or impressions <= 0:
            return {"ctr": None, "impressions": int(impressions),
                    "ctr_start_date": None, "ctr_data_through": None}
        weighted_percent = sum(row["impressions"] * row["ctr_percent"] for row in rows) / impressions
        return {"ctr": weighted_percent / 100, "impressions": int(impressions),
                "ctr_start_date": min(row["date"] for row in rows).isoformat(),
                "ctr_data_through": max(row["date"] for row in rows).isoformat()}

    def video_ctr(self, video_id, channel_id):
        rows = [row for row in self._reach_rows(channel_id) if row["video_id"] == video_id]
        return self._reach_summary(rows)

    def channel_ctr(self, channel_id):
        return self._reach_summary(self._reach_rows(channel_id))

    @staticmethod
    def _normal_start(start_date):
        try:
            parsed_start = datetime.fromisoformat(str(start_date)[:10]).date()
        except (TypeError, ValueError):
            parsed_start = date.today()
        return max(date(2008, 1, 1), min(parsed_start, date.today())).isoformat()

    def _activity(self, channel_id, start_date, video_id=""):
        end_date = date.today().isoformat()
        start_date = self._normal_start(start_date)
        base = {"ids": f"channel=={channel_id}", "startDate": start_date, "endDate": end_date,
                "maxResults": 1}
        if video_id:
            base["filters"] = f"video=={video_id}"
        activity = self._query({**base, "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,comments,likes"},
                               channel_id)
        sharing = self._query({**base, "dimensions": "sharingService", "metrics": "shares",
                               "maxResults": 25}, channel_id)
        names = activity.get("columnHeaders", [])
        values = activity.get("rows") or []
        result = dict(zip((item.get("name") for item in names), values[0] if values else []))
        share_rows = sharing.get("rows") or []
        share_headers = [item.get("name") for item in sharing.get("columnHeaders", [])]
        share_index = share_headers.index("shares") if "shares" in share_headers else None
        shares = sum(float(row[share_index]) for row in share_rows) if share_index is not None else None
        return result, shares, start_date, end_date

    def video_metrics(self, video_id, start_date, channel_id):
        result, shares, start_date, end_date = self._activity(channel_id, start_date, video_id)
        try:
            reach = self.video_ctr(video_id, channel_id)
            reach_warning = ("Chưa có báo cáo CTR được YouTube tạo. Báo cáo đầu tiên có thể cần 1-2 ngày."
                             if reach.get("ctr_data_through") is None else "")
        except DomainError as error:
            reach = {"ctr": None, "impressions": None, "ctr_start_date": None, "ctr_data_through": None}
            reach_warning = str(error)
        return {"views": result.get("views"), "watch_minutes": result.get("estimatedMinutesWatched"),
                "average_view_duration": result.get("averageViewDuration"),
                "average_view_percentage": result.get("averageViewPercentage"),
                "impressions": reach.get("impressions"), "ctr": reach.get("ctr"),
                "comments": result.get("comments"), "likes": result.get("likes"),
                "shares": shares, "video_id": video_id,
                "data_through": end_date, "start_date": start_date,
                "ctr_start_date": reach.get("ctr_start_date"),
                "ctr_data_through": reach.get("ctr_data_through"),
                "ctr_warning": reach_warning}

    def channel_metrics(self, channel_id, start_date):
        result, shares, start_date, end_date = self._activity(channel_id, start_date)
        try:
            reach = self.channel_ctr(channel_id)
            reach_warning = ("Chưa có báo cáo CTR được YouTube tạo. Báo cáo đầu tiên có thể cần 1-2 ngày."
                             if reach.get("ctr_data_through") is None else "")
        except DomainError as error:
            reach = {"ctr": None, "impressions": None, "ctr_start_date": None, "ctr_data_through": None}
            reach_warning = str(error)
        return {"views": result.get("views"), "watch_minutes": result.get("estimatedMinutesWatched"),
                "average_view_duration": result.get("averageViewDuration"),
                "average_view_percentage": result.get("averageViewPercentage"),
                "impressions": reach.get("impressions"), "ctr": reach.get("ctr"),
                "comments": result.get("comments"), "likes": result.get("likes"),
                "shares": shares, "channel_id": channel_id,
                "data_through": end_date, "start_date": start_date,
                "ctr_start_date": reach.get("ctr_start_date"),
                "ctr_data_through": reach.get("ctr_data_through"),
                "ctr_warning": reach_warning}
