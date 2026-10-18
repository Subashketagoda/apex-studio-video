import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.config import AppConfig

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

class YouTubePublisher:
    """Handles automated YouTube Shorts publishing via YouTube Data API v3."""

    def __init__(
        self,
        client_secrets_file: Optional[Path] = None,
        token_file: Optional[Path] = None
    ):
        self.client_secrets_file = client_secrets_file or AppConfig.YOUTUBE_CLIENT_SECRETS_FILE
        self.token_file = token_file or AppConfig.YOUTUBE_TOKEN_FILE

    def get_authenticated_service(self):
        """Authenticates with Google OAuth2 and returns YouTube service resource."""
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None
        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.client_secrets_file.exists():
                    raise FileNotFoundError(
                        f"YouTube OAuth client secrets file not found at '{self.client_secrets_file}'.\n"
                        "Please download OAuth 2.0 Client Secrets JSON from Google Cloud Console "
                        "and place it at the project root as 'client_secrets.json'."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secrets_file), SCOPES)
                creds = flow.run_local_server(port=0)

            # Save credentials for subsequent runs
            self.token_file.write_text(creds.to_json(), encoding="utf-8")

        return build("youtube", "v3", credentials=creds)

    def upload_short(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        privacy_status: str = "private",
    ) -> Dict[str, Any]:
        """
        Uploads an MP4 video file to YouTube as a Short.
        """
        path_obj = Path(video_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Video file not found at: {video_path}")

        # Ensure #shorts is present in tags and description for algorithm categorization
        all_tags = list(tags or [])
        if "#shorts" not in all_tags and "shorts" not in all_tags:
            all_tags.append("#shorts")

        if "#shorts" not in description:
            description = f"{description}\n\n#shorts"

        youtube = self.get_authenticated_service()

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": all_tags,
                "categoryId": "28",  # Science & Technology (default)
            },
            "status": {
                "privacyStatus": privacy_status,  # "private", "public", or "unlisted"
                "selfDeclaredMadeForKids": False,
            }
        }

        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(
            str(path_obj.resolve()),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 4  # 4MB chunks
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        print(f"🚀 Uploading Short to YouTube: '{title}' ({privacy_status})...")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"   Upload progress: {progress}%")

        video_id = response.get("id")
        video_url = f"https://youtube.com/shorts/{video_id}"
        print(f"🎉 Upload Complete! URL: {video_url}")

        return {
            "video_id": video_id,
            "url": video_url,
            "title": title,
            "privacy": privacy_status
        }
