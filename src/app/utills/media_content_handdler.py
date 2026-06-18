

import traceback
import base64
import mimetypes
import os
from pydub import AudioSegment




class MediaContentMixin:
    """Mixin class to provide media content handling functionality"""
    
    def _add_media_content_to_messages(self, path_images, path_files, path_audios):
        """Add media content to the messages from local paths only (URL support removed)."""
        try:
            has_images = path_images and len(path_images) > 0
            has_text_files = path_files and len(path_files) > 0
            has__audios = path_audios and len(path_audios) > 0

            # If no media content is available, return empty list
            if not any([has_images, has_text_files, has__audios]):
                return []

            enhanced_content = []

            if has_images:
                for image_path in path_images:
                    mime_type, _ = mimetypes.guess_type(image_path)
                    with open(image_path, "rb") as fh:
                        image_data = base64.b64encode(fh.read()).decode("utf-8")
                    enhanced_content.append({
                        "type": "image",
                        "source_type": "base64",
                        "data": image_data,
                        "mime_type": mime_type
                    })

            if has_text_files:
                for file_path in path_files:
                    mime_type, _ = mimetypes.guess_type(file_path)
                    with open(file_path, "rb") as fh:
                        file_data = base64.b64encode(fh.read()).decode("utf-8")
                    filename = os.path.basename(file_path)
                    enhanced_content.append({
                        "type": "file",
                        "source_type": "base64",
                        "data": file_data,
                        "mime_type": mime_type,
                        "filename": filename
                    })

            if has__audios:
                for audio_path in path_audios:
                    audio_type = os.path.splitext(audio_path)[1].lstrip(".")
                    with open(audio_path, "rb") as fh:
                        audio_data = base64.b64encode(fh.read()).decode("utf-8")
                    enhanced_content.append({
                        "type": "audio",
                        "source_type": "base64",
                        "data": audio_data,
                        "mime_type": f"audio/{audio_type}"
                    })

            return enhanced_content

        except Exception:
            tb_str = traceback.format_exc()
            print(f"Error in _add_media_content_to_messages:\n{tb_str}")
            return []
