"""
Where the sound comes from: what this machine is playing, or a file.

Deliberately not the stream's URL. Downloading from YouTube is against its
terms, and the request was "only based on the audio": whatever a person is
watching already reaches the sound card, whichever site it came from.
"""

import os
import re
import subprocess
import time
from typing import Iterator

import numpy as np

SAMPLE_RATE = 16_000

CHUNK_SECONDS = 0.25


def find_stream(app: str, listing: str | None = None) -> str | None:
    """
    The index of the playing stream whose application matches `app`.

    Parses `pactl list sink-inputs` as text: `--format=json` only exists
    from PulseAudio 16, and Ubuntu 22.04 ships 15.99.
    """

    if listing is None:
        listing = subprocess.run(
            ["pactl", "list", "sink-inputs"],
            capture_output=True,
            text=True,
            check=True,
            # This machine's pactl answers in Spanish otherwise.
            env={**os.environ, "LC_ALL": "C"},
        ).stdout

    found = None

    # A browser holds a stream per tab, some of them silent and corked;
    # the last one that matches and is playing is the one just started.
    for block in re.split(r"\n(?=\S.*#\d+)", listing):

        index = re.search(r"#(\d+)", block)
        names = re.findall(
            r'application\.(?:name|process\.binary) = "([^"]*)"', block
        )

        if not index or not any(app.lower() in name.lower() for name in names):
            continue

        if re.search(r"Corked:\s*yes", block):
            continue

        found = index.group(1)

    return found


class SystemAudio:
    """
    What the sound card is playing, as float32 mono at 16 kHz.

    `app` listens to one application's stream only, so a notification or
    another tab stays out of the transcript; without it, the default
    sink's monitor hears everything the machine plays. The microphone is
    never opened.
    """

    # A YouTube live stream's player can replace its audio stream (an ad,
    # a reconnect), which ends a --monitor-stream capture. Look again
    # rather than stop listening.
    RECONNECT_SECONDS = 2.0

    def __init__(self, app: str | None = None):
        self.app = app
        self.process: subprocess.Popen | None = None
        self.stopped = False

    def _command(self) -> list[str]:

        command = [
            "parec",
            "--format=s16le",
            f"--rate={SAMPLE_RATE}",
            "--channels=1",
            "--latency-msec=200",
            "--raw",
        ]

        if self.app is None:
            return command + ["--device=@DEFAULT_MONITOR@"]

        stream = find_stream(self.app)

        if stream is None:
            return []

        return command + [f"--monitor-stream={stream}"]

    def chunks(self) -> Iterator[np.ndarray]:

        size = int(SAMPLE_RATE * CHUNK_SECONDS) * 2

        while not self.stopped:

            command = self._command()

            if not command:
                # Nothing playing yet: the clock still runs, so that
                # timestamps stay true to the conversation.
                yield np.zeros(size // 2, dtype=np.float32)
                time.sleep(CHUNK_SECONDS)
                continue

            self.process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )

            while not self.stopped:

                raw = self.process.stdout.read(size)

                if len(raw) < size:
                    break

                yield np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768

            self.process.wait()

            if not self.stopped:
                time.sleep(self.RECONNECT_SECONDS)

    def stop(self) -> None:

        self.stopped = True

        if self.process is not None and self.process.poll() is None:
            self.process.terminate()


class FileAudio:
    """
    A recording, optionally paced as if it were live. The way to test the
    tool without a stream, and to run it again over a saved conversation.
    """

    def __init__(self, path: str, realtime: bool = False):
        self.path = path
        self.realtime = realtime
        self.stopped = False

    def chunks(self) -> Iterator[np.ndarray]:

        # faster-whisper decodes with PyAV, so any format reads without a
        # system ffmpeg, which this machine does not have.
        from faster_whisper import decode_audio

        audio = decode_audio(self.path, sampling_rate=SAMPLE_RATE)

        size = int(SAMPLE_RATE * CHUNK_SECONDS)

        for start in range(0, len(audio), size):

            if self.stopped:
                return

            yield audio[start : start + size]

            if self.realtime:
                time.sleep(CHUNK_SECONDS)

    def stop(self) -> None:
        self.stopped = True
