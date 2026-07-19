import os
import uuid
from omnimash.storage.gcs import GcsStorageManager


class VideoStitcher:
    def __init__(self, mock_mode: bool = True, bucket_name: str | None = None):
        self.mock_mode = mock_mode
        self.storage = GcsStorageManager(
            bucket_name=bucket_name, mock_mode=self.mock_mode
        )

    def concatenate_clips(self, clip_paths: list[str], output_dir: str = "/tmp") -> str:
        master_filename = f"master_{uuid.uuid4().hex[:8]}_stitched.mp4"
        out_path = os.path.join(output_dir, master_filename)

        if self.mock_mode:
            os.makedirs(output_dir, exist_ok=True)
            with open(out_path, "w") as f:
                f.write("mock mp4 master video content")

        self.storage.upload_file(
            out_path, destination_blob_name=f"master/{master_filename}"
        )
        return out_path
