import os
import shutil
import subprocess
import uuid

from omnimash.storage.gcs import GcsStorageManager


class VideoStitcher:
    def __init__(self, mock_mode: bool = True, bucket_name: str | None = None):
        self.mock_mode = mock_mode
        self.storage = GcsStorageManager(bucket_name=bucket_name, mock_mode=self.mock_mode)

    def concatenate_clips(
        self,
        clip_paths: list[str],
        output_dir: str = "/tmp",
        session_id: str | None = None,
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
            if clip_paths:
                concat_list_path = os.path.join(output_dir, "concat_list.txt")
                with open(concat_list_path, "w") as f:
                    for clip in clip_paths:
                        abs_path = os.path.abspath(clip)
                        f.write(f"file '{abs_path}'\n")

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
