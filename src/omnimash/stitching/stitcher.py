import os
import shutil
import tempfile
import uuid

from omnimash.engine.media_utils import (
    DEFAULT_FFMPEG_TIMEOUT,
    FfmpegError,
    ffmpeg_ok,
    run_ffmpeg,
)
from omnimash.storage.gcs import GcsStorageManager


class VideoStitcher:
    def __init__(self, mock_mode: bool = True, bucket_name: str | None = None):
        self.mock_mode = mock_mode
        self.storage = GcsStorageManager(bucket_name=bucket_name, mock_mode=self.mock_mode)

    def concatenate_clips(
        self,
        clip_paths: list[str],
        output_dir: str | None = None,
        session_id: str | None = None,
    ) -> str:
        output_dir = output_dir or tempfile.gettempdir()
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
            if clip_paths:
                # Unique concat-list name so concurrent stitches never clobber
                # each other's list; removed in the finally below.
                concat_list_path = os.path.join(
                    output_dir, f"concat_list_{uuid.uuid4().hex[:8]}.txt"
                )
                try:
                    with open(concat_list_path, "w") as f:
                        for clip in clip_paths:
                            abs_path = os.path.abspath(clip)
                            # ffmpeg concat demuxer wraps paths in single quotes;
                            # escape any embedded quote so odd filenames don't
                            # corrupt the list.
                            escaped = abs_path.replace("'", "'\\''")
                            f.write(f"file '{escaped}'\n")

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
                    # Try a fast stream copy first; fall back to a re-encode when
                    # the clips' codecs differ. The re-encode raises FfmpegError
                    # on failure so we never upload a broken/empty master.
                    if not ffmpeg_ok(cmd_copy, timeout=DEFAULT_FFMPEG_TIMEOUT):
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
                        run_ffmpeg(cmd_reencode, timeout=DEFAULT_FFMPEG_TIMEOUT)
                finally:
                    try:
                        if os.path.exists(concat_list_path):
                            os.remove(concat_list_path)
                    except OSError:
                        pass

        # Never upload a master that ffmpeg failed to produce.
        if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
            raise FfmpegError(f"Stitched master missing or empty: {out_path}")

        gcs_blob = self.storage.build_session_blob_path(
            session_id=session_id,
            category="final_masters",
            filename=master_filename,
        )
        self.storage.upload_file(out_path, destination_blob_name=gcs_blob)
        return out_path
