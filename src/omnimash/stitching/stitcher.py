import os
import uuid


class VideoStitcher:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode

    def concatenate_clips(self, clip_paths: list[str], output_dir: str = "/tmp") -> str:
        master_filename = f"master_{uuid.uuid4().hex[:8]}_stitched.mp4"
        out_path = os.path.join(output_dir, master_filename)

        if self.mock_mode:
            os.makedirs(output_dir, exist_ok=True)
            with open(out_path, "w") as f:
                f.write("mock mp4 master video content")
            return out_path

        return out_path
