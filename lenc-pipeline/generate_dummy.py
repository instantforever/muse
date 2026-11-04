#!/usr/bin/env python3
"""Stand-in for an image/video/text/audio GENERATOR.
Creates files whose exact bytes the assistant never sees: content derives
from os.urandom inside this process. Only names+sizes are reported."""
import os, random, struct, sys, wave, zlib

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
rng = random.Random(os.urandom(16))
report = []

# text: pseudo-sentences built from random syllables
syl = ["ka", "mi", "so", "ra", "yu", "me", "ha", "na", "to", "ri", "se", "wo"]
txt = " ".join("".join(rng.choice(syl) for _ in range(rng.randint(2, 6)))
               for _ in range(400)) + "\n"
p = os.path.join(out, "note.txt"); open(p, "w").write(txt)
report.append(("note.txt", os.path.getsize(p)))

# image: a valid PNG with random noise pixels (stdlib only)
w = h = 64
raw = b"".join(b"\x00" + os.urandom(w * 3) for _ in range(h))
def chunk(t, d):
    c = struct.pack(">I", len(d)) + t + d
    return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
png = (b"\x89PNG\r\n\x1a\n"
       + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
p = os.path.join(out, "image.png"); open(p, "wb").write(png)
report.append(("image.png", os.path.getsize(p)))

# audio: a valid WAV, sine tone at a random frequency
freq = rng.choice([220, 330, 440, 554, 659])
sr = 22050
frames = b"".join(struct.pack("<h", int(12000 * ((i % 100) / 100.0 - 0.5)))
                  for i in range(sr))
p = os.path.join(out, "voice.wav")
with wave.open(p, "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
    wf.writeframes(frames)
report.append(("voice.wav", os.path.getsize(p)))

# video: byte-blob stand-in (encryption is codec-agnostic; a real generator
# such as ffmpeg or a TTS/video backend plugs in at exactly this point)
p = os.path.join(out, "clip.mp4")
open(p, "wb").write(b"\x00\x00\x00\x18ftypmp42" + os.urandom(512 * 1024))
report.append(("clip.mp4", os.path.getsize(p)))

for name, size in report:
    print(f"generated {name} {size} bytes")
