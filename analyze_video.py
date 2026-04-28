"""
Extract frames from a .mov video and analyze each with Claude vision API.
Usage: uv run python analyze_video.py <video_path> [--fps 1] [--out /tmp/frames]
"""
import argparse
import base64
import os
import subprocess
import sys
import anthropic

def extract_frames(video_path: str, output_dir: str, fps: float = 1.0) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    pattern = os.path.join(output_dir, "frame_%04d.jpg")
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",
        pattern, "-y"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    frames = sorted([
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.startswith("frame_") and f.endswith(".jpg")
    ])
    print(f"Extracted {len(frames)} frames")
    return frames


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def analyze_frames(frames: list[str], question: str) -> str:
    client = anthropic.Anthropic()

    content = []
    for i, frame_path in enumerate(frames):
        content.append({
            "type": "text",
            "text": f"Frame {i+1} of {len(frames)}:"
        })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": encode_image(frame_path),
            }
        })

    content.append({
        "type": "text",
        "text": question
    })

    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        messages=[{"role": "user", "content": content}]
    )
    return message.content[0].text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="Path to .mov video file")
    parser.add_argument("--fps", type=float, default=0.5, help="Frames per second to extract (default: 0.5 = 1 frame every 2s)")
    parser.add_argument("--out", default="/tmp/video_frames", help="Directory to store extracted frames")
    parser.add_argument("--question", default=(
        "These are sequential frames from a screen recording. "
        "Describe what the user is trying to do, what UI elements are visible, "
        "what fields are filled or empty, what errors or blockers are shown, "
        "and summarize the key issue being demonstrated."
    ))
    args = parser.parse_args()

    print(f"Extracting frames from: {args.video}")
    frames = extract_frames(args.video, args.out, args.fps)

    if not frames:
        print("No frames extracted.", file=sys.stderr)
        sys.exit(1)

    # Claude has image limits — cap at 20 frames
    if len(frames) > 20:
        step = len(frames) // 20
        frames = frames[::step][:20]
        print(f"Sampled down to {len(frames)} frames for API limit")

    print(f"Sending {len(frames)} frames to Claude for analysis...")
    result = analyze_frames(frames, args.question)

    print("\n=== ANALYSIS ===\n")
    print(result)

    out_file = "/tmp/video_analysis.txt"
    with open(out_file, "w") as f:
        f.write(result)
    print(f"\nSaved to {out_file}")


if __name__ == "__main__":
    main()
