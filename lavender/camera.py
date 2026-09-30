"""Cameras return a JPEG snapshot, or None when there is no camera."""

from __future__ import annotations


class NullCamera:
    def snapshot(self) -> bytes | None:
        return None

    def close(self) -> None:
        pass


class OpenCVCamera:
    """Webcam via OpenCV (`pip install open-lavender[camera]`)."""

    def __init__(self, index: int = 0, max_side: int = 768) -> None:
        import cv2

        self._cv2 = cv2
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise IOError(f"could not open camera {index}")
        self.max_side = max_side

    def snapshot(self) -> bytes | None:
        ok, frame = self.cap.read()
        if not ok:
            return None
        h, w = frame.shape[:2]
        scale = self.max_side / max(h, w)
        if scale < 1:
            frame = self._cv2.resize(frame, (int(w * scale), int(h * scale)))
        ok, jpeg = self._cv2.imencode(".jpg", frame, [self._cv2.IMWRITE_JPEG_QUALITY, 85])
        return jpeg.tobytes() if ok else None

    def close(self) -> None:
        self.cap.release()
