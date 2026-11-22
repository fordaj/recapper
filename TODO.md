```python
import yaml, sys, argparse, subprocess, shutil
from pathlib import Path

try:
    import concatenate
    import title
except:
    from . import concatenate
    from . import title


def images_to_side_by_side_video(
    left_image: Path, right_image: Path, output: Path, duration: int = 5
):
    filter_complex = (
        "[0:v]scale=w=960:h=1080:force_original_aspect_ratio=increase,"
        "crop=960:1080,setsar=1[img1];"
        "[1:v]scale=w=960:h=1080:force_original_aspect_ratio=increase,"
        "crop=960:1080,setsar=1[img2];"
        "[img1][img2]hstack=inputs=2[out]"
    )

    cmd = [
        "ffmpeg",
        "-loop",
        "1",
        "-t",
        "5",
        "-i",
        str(left_image),
        "-loop",
        "1",
        "-t",
        str(duration),
        "-i",
        str(right_image),
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output),
        "-y",
    ]

    print(f"Creating side-by-side video {output} from {left_image} and {right_image}")
    subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def overlay_audio(input_mp4_file: Path, input_mp3_file: Path):
    # Make tmp dir
    tmpdir = Path.cwd() / ".tmp" / "overlay_audio"
    tmpdir.mkdir(parents=True, exist_ok=True)

    # Copy to tmp dir
    tmp_input_mp4_file = input_mp4_file.rename(tmpdir / input_mp4_file.name)
    tmp_input_mp3_file = tmpdir / input_mp3_file.name
    shutil.copy2(input_mp3_file, tmp_input_mp3_file)

    cmd = [
        "ffmpeg",
        "-i",
        str(tmp_input_mp4_file),
        "-i",
        str(tmp_input_mp3_file),
        "-filter_complex",
        "[0:a][1:a]amix=inputs=2:dropout_transition=0[a]",
        "-map",
        "0:v",
        "-map",
        "[a]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(input_mp4_file),
        "-y",
    ]
    print(f"Overlaying audio {input_mp3_file} onto {input_mp4_file}")
    # print(" ".join(cmd))
    subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    # Delete temp dir
    shutil.rmtree(tmpdir)


def image_to_video(input: Path, output: Path, duration: int = 5):
    cmd = [
        "ffmpeg",
        "-loop",
        "1",
        "-i",
        str(input),
        "-t",
        str(duration),
        "-vf",
        "setsar=1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output),
        "-y",
    ]
    print(f"Converting {input} to {output}")

    subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def run(file: Path):
    with open(file, "r") as f:
        data = yaml.safe_load(f)

        for entry in data:
            concatenate_dict = entry.get("concatenate")
            if concatenate_dict:
                audio = concatenate_dict.get("audio")
                videos = concatenate_dict.get("videos")
                videos_to_concatenate = []
                for video in videos:
                    if type(video) == str:
                        videos_to_concatenate.append(Path(video))
                    elif list(video.keys())[0] == "title-slide":
                        title.run_ffmpeg(
                            duration=video.get("duration", 5),
                            color=video.get("color", "black"),
                            title=video.get("title"),
                            subtitle=video.get("subtitle", ""),
                            output_file=video.get("output-file"),
                        )
                        videos_to_concatenate.append(Path(video.get("output-file")))
                    elif list(video.keys())[0] == "image-to-video":
                        image_to_video(
                            duration=video.get("duration", 5),
                            input=video.get("input"),
                            output=video.get("output"),
                        )
                        videos_to_concatenate.append(Path(video.get("output")))
                    elif list(video.keys())[0] == "images-to-side-by-side-video":
                        images_to_side_by_side_video(
                            left_image=video.get("left-image"),
                            right_image=video.get("right-image"),
                            duration=video.get("duration", 5),
                            output=video.get("output", 5),
                        )
                        videos_to_concatenate.append(Path(video.get("output")))
                output_file = concatenate_dict.get("output-file")
                concatenate.run_from_list(videos_to_concatenate, output_file, 4)
                if audio:
                    audio_to_concatenate = []
                    for entry in audio:
                        if type(entry) == str:
                            audio_to_concatenate.append(Path(entry))
                    input_mp3 = Path(audio_to_concatenate[0])
                    overlay_audio(Path(output_file), input_mp3)


def setup_parser(parser):
    parser.description = "Process commands from a YAML file."
    parser.add_argument("file", type=str, help="Input YAML file path.")
    parser.add_argument(
        "--retain-temp", action="store_true", help="Retain temporary files."
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print ffmpeg command data."
    )
    return parser


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser()
    setup_parser(parser)
    args = parser.parse_args(args)
    run(args.file)

    # run_ffmpeg(args.duration, args.color, args.output_file, args.title, args.subtitle)


if __name__ == "__main__":
    main()
```

```python
import subprocess, sys, argparse, shutil, time, glob
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


def run(cmd):
    subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def ensure_tmp_dir(base):
    tmp = base / ".tmp" / "concatenate"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


def collect_inputs(pattern):
    paths = sorted(Path(p) for p in glob.glob(pattern))
    if not paths:
        raise RuntimeError("No input files matched.")
    return paths


def normalize_single(p, out_dir):
    out = out_dir / p.name

    # Probe input for audio
    has_audio = False
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "csv=p=0",
                str(p),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        has_audio = bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        has_audio = False

    if has_audio:
        # Normal case: re-encode video and audio
        cmd = [
            "ffmpeg",
            "-i",
            str(p),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-level",
            "4.0",
            "-r",
            "30",
            "-fps_mode",
            "cfr",
            "-fflags",
            "+genpts",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(out),
            "-y",
        ]
    else:
        # Add silent audio: two inputs, map video and audio
        cmd = [
            "ffmpeg",
            "-i",
            str(p),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-level",
            "4.0",
            "-r",
            "30",
            "-fps_mode",
            "cfr",
            "-fflags",
            "+genpts",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            str(out),
            "-y",
        ]

    run(cmd)
    return out


def normalize_timestamps(files, out_dir, workers=16):
    normalized = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(normalize_single, f, out_dir) for f in files]
        for future in futures:
            normalized.append(future.result())
    return normalized


def write_concat_list(files, list_path):
    with list_path.open("w", encoding="utf-8") as f:
        for p in files:
            f.write(f"file '{p.as_posix()}'\n")


def concat(list_path, output):
    cmd = [
        "ffmpeg",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        str(output),
        "-y",
    ]
    run(cmd)


def setup_parser(parser):
    parser.description = "Concatenate videos with timestamp normalization (parallel)."
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input-glob", help="Glob pattern for input files")
    group.add_argument(
        "--input-list",
        help="Path to file containing newline separated list of files to concatenate",
    )
    parser.add_argument(
        "--output", default=None, help="Output file (default: output<TIMESTAMP>.mp4)."
    )
    parser.add_argument(
        "--workers", type=int, default=4, help="Number of parallel ffmpeg jobs."
    )
    return parser


def run_from_glob(input_glob, output, workers):
    input_list = collect_inputs(input_glob)
    run_from_list(input_list, output, workers)


def run_from_list(input_list: list[Path], output, workers):

    tmp = ensure_tmp_dir(Path.cwd())

    normalized = normalize_timestamps(input_list, tmp, workers=workers)

    list_path = tmp / "list.txt"
    write_concat_list(normalized, list_path)

    concat(list_path, tmp / output)
    normalize_timestamps([tmp / output], Path.cwd())

    shutil.rmtree(tmp)


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser()
    setup_parser(parser)
    args = parser.parse_args(args)
    if args.output:
        output = Path(args.output)
    else:
        ts = int(time.time())
        output = Path.cwd() / f"output{ts}.mp4"
    if args.input_glob:
        run_from_glob(args.input_glob, output, args.workers)
    else:  # args.input_list
        run_from_list(args.input_list, output, args.workers)


if __name__ == "__main__":
    main()

```

```python
import subprocess, sys, argparse
from pathlib import Path


def run_ffmpeg(duration, color, output_file, title, subtitle):
    vf = (
        f"drawtext=text='{title}':fontfile=/path/to/font.ttf:"
        f"x=(w-text_w)/2:y=(h/2-50):fontsize=72:fontcolor=white,"
        f"drawtext=text='{subtitle}':fontfile=/path/to/font.ttf:"
        f"x=(w-text_w)/2:y=(h/2+50):fontsize=48:fontcolor=white,"
        f"fade=t=in:st=0:d=1,fade=t=out:st={duration-1}:d=1"
    )

    cmd = [
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=1920x1080:d={duration}",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout=stereo:sample_rate=48000",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        output_file,
        "-y",
    ]
    subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def setup_parser(parser):
    parser.description = "Generate a title slide."
    parser.add_argument(
        "--duration", type=int, default=5, help="Video duration in seconds (default 5)."
    )
    parser.add_argument(
        "--color", default="black", help="Background color (default black)."
    )
    parser.add_argument("--output-file", required=True, help="Output video file path.")
    parser.add_argument("--title", required=True, help="Main title text.")
    parser.add_argument("--subtitle", required=True, help="Subtitle text.")
    return parser


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser()
    setup_parser(parser)
    args = parser.parse_args(args)

    run_ffmpeg(args.duration, args.color, args.output_file, args.title, args.subtitle)


if __name__ == "__main__":
    main()

```

```yaml
- concatenate:
    output-file: "concatenated_video.mp4"
    audio:
      - "Oldies Station.mp3"
    videos:
      - "00.mp4"
      - title-slide:
        title: "Ford Family Recap"
        subtitle: "2025"
        output-file: "00.mp4"
      - image-to-video:
        input: "./72.jpeg"
        duration: 5
        output: "./72.mp4"
      - images-to-side-by-side-video:
        left-image: "./72.jpeg"
        right-image: "./72.jpeg"
        duration: 5
        output: "./side-by-side.mp4"
```
