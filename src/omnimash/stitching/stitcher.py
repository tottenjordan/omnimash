import os
import shutil
import subprocess
import uuid
from omnimash.storage.gcs import GcsStorageManager


class VideoStitcher:
    def __init__(self, mock_mode: bool = True, bucket_name: str | None = None):
        self.mock_mode = mock_mode
        self.storage = GcsStorageManager(
            bucket_name=bucket_name, mock_mode=self.mock_mode
        )

    def concatenate_clips(
        self,
        clip_paths: list[str],
        output_dir: str = "/tmp",
        session_id: str | None = None,
        master_audio_path: str | None = None,
    ) -> str:
        os.makedirs(output_dir, exist_ok=True)
        master_filename = f"master_{uuid.uuid4().hex[:8]}_stitched.mp4"
        out_path = os.path.join(output_dir, master_filename)

        if self.mock_mode:
            if clip_paths and os.path.exists(clip_paths[0]):
                shutil.copyfile(clip_paths[0], out_path)
            else:
                with open(out_path, "w") as f:
                    f.write("mock mp4 master video content")
        else:
            resolved_clips: list[str] = []
            for clip in clip_paths:
                norm_clip = self.storage._normalize_media_source_path(clip)
                if os.path.exists(norm_clip):
                    resolved_clips.append(os.path.abspath(norm_clip))
                elif norm_clip.startswith("/static/"):
                    loc = os.path.join(os.getcwd(), norm_clip.lstrip("/"))
                    if os.path.exists(loc):
                        resolved_clips.append(loc)
                elif (
                    not self.mock_mode
                    and self.storage._bucket
                    and norm_clip.startswith("gs://")
                ):
                    try:
                        blob_name = norm_clip.replace(
                            f"gs://{self.storage.bucket_name}/", ""
                        ).lstrip("/")
                        tmp_clip_path = os.path.join(
                            output_dir, f"clip_{uuid.uuid4().hex[:6]}.mp4"
                        )
                        blob = self.storage._bucket.blob(blob_name)
                        blob.download_to_filename(tmp_clip_path)
                        resolved_clips.append(tmp_clip_path)
                    except Exception:
                        resolved_clips.append(norm_clip)
                else:
                    resolved_clips.append(norm_clip)

            resolved_audio: str | None = None
            if master_audio_path:
                norm_audio = self.storage._normalize_media_source_path(master_audio_path)
                if os.path.exists(norm_audio):
                    resolved_audio = os.path.abspath(norm_audio)
                elif norm_audio.startswith("/static/"):
                    loc = os.path.join(os.getcwd(), norm_audio.lstrip("/"))
                    if os.path.exists(loc):
                        resolved_audio = loc
                elif (
                    not self.mock_mode
                    and self.storage._bucket
                    and norm_audio.startswith("gs://")
                ):
                    try:
                        blob_name = norm_audio.replace(
                            f"gs://{self.storage.bucket_name}/", ""
                        ).lstrip("/")
                        tmp_audio_path = os.path.join(
                            output_dir, f"audio_{uuid.uuid4().hex[:6]}.mp3"
                        )
                        blob = self.storage._bucket.blob(blob_name)
                        blob.download_to_filename(tmp_audio_path)
                        resolved_audio = tmp_audio_path
                    except Exception:
                        resolved_audio = norm_audio
                else:
                    resolved_audio = norm_audio

            if resolved_clips:
                concat_list_path = os.path.join(output_dir, "concat_list.txt")
                with open(concat_list_path, "w") as f:
                    for clip_file in resolved_clips:
                        f.write(f"file '{clip_file}'\n")

                if resolved_audio and os.path.exists(resolved_audio):
                    cmd_copy = [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        concat_list_path,
                        "-i",
                        resolved_audio,
                        "-c:v",
                        "copy",
                        "-c:a",
                        "aac",
                        "-map",
                        "0:v:0",
                        "-map",
                        "1:a:0",
                        "-shortest",
                        out_path,
                    ]
                else:
                    cmd_copy = [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        concat_list_path,
                        "-c",
                        "copy",
                        out_path,
                    ]

                res = subprocess.run(cmd_copy, capture_output=True, text=True)
                if res.returncode != 0:
                    if resolved_audio and os.path.exists(resolved_audio):
                        cmd_reencode = [
                            "ffmpeg",
                            "-y",
                            "-f",
                            "concat",
                            "-safe",
                            "0",
                            "-i",
                            concat_list_path,
                            "-i",
                            resolved_audio,
                            "-c:v",
                            "libx264",
                            "-c:a",
                            "aac",
                            "-map",
                            "0:v:0",
                            "-map",
                            "1:a:0",
                            "-pix_fmt",
                            "yuv420p",
                            "-shortest",
                            out_path,
                        ]
                    else:
                        cmd_reencode = [
                            "ffmpeg",
                            "-y",
                            "-f",
                            "concat",
                            "-safe",
                            "0",
                            "-i",
                            concat_list_path,
                            "-c:v",
                            "libx264",
                            "-c:a",
                            "aac",
                            "-pix_fmt",
                            "yuv420p",
                            out_path,
                        ]
                    subprocess.run(cmd_reencode, capture_output=True, text=True)

        gcs_blob = self.storage.build_session_blob_path(
            session_id=session_id,
            category="final_masters",
            filename=master_filename,
        )
        self.storage.upload_file(out_path, destination_blob_name=gcs_blob)
        return out_path
