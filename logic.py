import typer
import srt
import json
import sys
import datetime
import ffmpeg
import os
import tempfile
from pathlib import Path
from typing_extensions import Annotated

app = typer.Typer()


def _get_draft_path(srt_path: Path) -> Path:
    """
    Returns the standard path to the draft file
    from the original SRT file.
    """
    return srt_path.with_suffix(srt_path.suffix + ".draft.json")


def _load_draft_data(draft_path: Path) -> dict:
    """
    Auxiliar function to load the draft data.
    """
    try:
        with open(draft_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading draft file: {e}", file=sys.stderr)
        raise typer.Exit(code=1)


def _save_draft_data(draft_path: Path, data: dict):
    """
    Auxiliar function to save data to the draft file.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if "metadata" not in data:
        data["metadata"] = {}

    data["metadata"]["updated_at"] = now_utc

    try:
        with open(draft_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving updated draft file: {e}", file=sys.stderr)
        raise typer.Exit(code=1)


def _create_draft_from_srt(srt_path: Path, draft_path: Path) -> dict:
    """
    Reads a SRT and creates a JSON draft file.
    """
    try:
        with open(srt_path, "r", encoding="utf-8") as f:
            subtitles_list = list(srt.parse(f.read()))
    except Exception as e:
        print(f"Error reading SRT file: {e}", file=sys.stderr)
        raise typer.Exit(code=1)

    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    draft_data = {
        "metadata": {
            "original_lang": "unknown",
            "target_lang": "unknown",
            "created_at": now_utc,
            "updated_at": now_utc,
        },
        "subtitles": [],
    }

    for sub in subtitles_list:
        draft_data["subtitles"].append(
            {
                "index": sub.index,
                "start_seconds": sub.start.total_seconds(),
                "end_seconds": sub.end.total_seconds(),
                "original": sub.content,
                "translation": "",
                "status": "unverified",
            }
        )

    _save_draft_data(draft_path, draft_data)
    return draft_data


def _build_srt_list(subtitles_list: list, content_key: str) -> list[srt.Subtitle]:
    """
    Auxiliar function to convert a JSON dict to a list of
    srt.Subtitle objects.
    """
    srt_list = []
    for entry in subtitles_list:
        content = entry.get(content_key) or "..."

        new_sub = srt.Subtitle(
            index=entry["index"],
            start=datetime.timedelta(seconds=entry["start_seconds"]),
            end=datetime.timedelta(seconds=entry["end_seconds"]),
            content=content,
        )
        srt_list.append(new_sub)

    return srt_list


def _find_entry_by_index(subtitles_list: list, index: int) -> dict | None:
    """
    Finds a subtitle entry in a list by its index.
    """
    for entry in subtitles_list:
        if entry["index"] == index:
            return entry
    return None


@app.command()
def load(
    srt_file: Annotated[
        Path, typer.Argument(exists=True, help="Path to the original .srt file.")
    ],
):
    """
    Loads a SRT file. If a draft already exists, loads it.
    If not, creates one from the SRT file.
    Prints the resulting JSON data to stdout.
    """
    draft_path = _get_draft_path(srt_file)

    if draft_path.exists():
        data = _load_draft_data(draft_path)
    else:
        print(f"Creating new draft file at {draft_path}", file=sys.stderr)
        data = _create_draft_from_srt(srt_file, draft_path)

    print(json.dumps(data, ensure_ascii=False))


@app.command()
def translate(
    draft_file: Annotated[
        Path, typer.Argument(exists=True, help="Path to the .draft.json file.")
    ],
    index: Annotated[int, typer.Option(help="The index of the subtitle to update.")],
    text: Annotated[str, typer.Option(help="The new translation text.")],
):
    """
    Updates the translation for a single entry in the draft file.
    """
    data = _load_draft_data(draft_file)

    entry = _find_entry_by_index(data["subtitles"], index)

    if not entry:
        print(f"Error: No entry found with index {index}", file=sys.stderr)
        raise typer.Exit(code=1)

    entry["translation"] = text
    entry["status"] = "verified"

    _save_draft_data(draft_file, data)

    print(
        json.dumps({"status": "success", "updated_index": index, "action": "translate"})
    )


@app.command()
def fix(
    draft_file: Annotated[
        Path, typer.Argument(exists=True, help="Path to the .draft.json file.")
    ],
    index: Annotated[int, typer.Option(help="The index of the subtitle to update.")],
    text: Annotated[str, typer.Option(help="The new original text.")],
):
    """
    Updates the original text for a single entry in the draft file.
    """
    data = _load_draft_data(draft_file)

    entry = _find_entry_by_index(data["subtitles"], index)

    if not entry:
        print(f"Error: No entry found with index {index}", file=sys.stderr)
        raise typer.Exit(code=1)

    entry["original"] = text
    entry["status"] = "unverified"

    _save_draft_data(draft_file, data)

    print(json.dumps({"status": "success", "updated_index": index, "action": "fix"}))


@app.command()
def config(
    draft_file: Annotated[
        Path, typer.Argument(exists=True, help="Path to the .draft.json file.")
    ],
    lang_orig: Annotated[
        str, typer.Option(help="The original language code (e.g., en-US)")
    ] = None,
    lang_target: Annotated[
        str, typer.Option(help="The target language code (e.g., pt-BR)")
    ] = None,
    audio_file: Annotated[
        Path, typer.Option(exists=True, help="The path to the original audio file.")
    ] = None,
):
    """
    Updates the language metadata in the draft file.
    """
    if not lang_orig and not lang_target and not audio_file:
        print(f"You must provide at least one option to configure.", file=sys.stderr)
        raise typer.Exit(code=1)

    data = _load_draft_data(draft_file)

    if lang_orig:
        data["metadata"]["original_lang"] = lang_orig
    if lang_target:
        data["metadata"]["target_lang"] = lang_target
    if audio_file:
        data["metadata"]["audio_file"] = str(audio_file.resolve())

    _save_draft_data(draft_file, data)
    print(json.dumps({"status": "success", "action": "config"}))


@app.command()
def status_toggle(
    draft_file: Annotated[
        Path, typer.Argument(exists=True, help="Path to the .draft.json file.")
    ],
    index: Annotated[int, typer.Option(help="The index of the subtitle to update.")],
):
    """
    Toggles the status of a single entry in the draft file.
    """
    data = _load_draft_data(draft_file)

    entry = _find_entry_by_index(data["subtitles"], index)

    if not entry:
        print(f"Error: No entry found with index {index}", file=sys.stderr)
        raise typer.Exit(code=1)

    entry["status"] = "verified" if entry["status"] == "unverified" else "unverified"

    _save_draft_data(draft_file, data)
    print(
        json.dumps(
            {"status": "success", "updated_index": index, "action": "status_toggle"}
        )
    )


@app.command()
def export(
    draft_file: Annotated[
        Path, typer.Argument(exists=True, help="Path to the .draft.json file.")
    ],
):
    """
    Exports the draft file to two SRT files:
    One for the original language and one for the target language.
    """
    data = _load_draft_data(draft_file)
    subtitles_list = data["subtitles"]

    original_srt_list = _build_srt_list(subtitles_list, content_key="original")
    target_srt_list = _build_srt_list(subtitles_list, content_key="translation")

    original_srt_content = srt.compose(original_srt_list)
    target_srt_content = srt.compose(target_srt_list)

    original_srt_name = draft_file.name.removesuffix(".draft.json")
    base_name = Path(original_srt_name).stem

    lang_orig = data["metadata"].get("original_lang", "original")
    lang_target = data["metadata"].get("target_lang", "target")

    if lang_orig == "unknown":
        lang_orig = "original"
    if lang_target == "unknown":
        lang_target = "target"

    out_orig_path = draft_file.with_name(f"{base_name}_{lang_orig}.srt")
    out_target_path = draft_file.with_name(f"{base_name}_{lang_target}.srt")

    try:
        with open(out_orig_path, "w", encoding="utf-8") as f:
            f.write(original_srt_content)
        with open(out_target_path, "w", encoding="utf-8") as f:
            f.write(target_srt_content)
    except Exception as e:
        print(f"Error writing SRT files: {e}", file=sys.stderr)
        raise typer.Exit(code=1)

    print(
        json.dumps(
            {
                "status": "success",
                "original_file": str(out_orig_path),
                "target_file": str(out_target_path),
                "action": "export",
            }
        )
    )


@app.command()
def play(
    draft_file: Annotated[
        Path, typer.Argument(exists=True, help="Path to the .draft.json file.")
    ],
    index: Annotated[int, typer.Option(help="The index of the subtitle to play.")],
):
    """
    Extracts a small audio clip for the given index
    and prints the path to the temporary clip.
    """
    data = _load_draft_data(draft_file)

    audio_file_path = data["metadata"].get("audio_file")
    if not audio_file_path:
        print(
            f"Error: Audio file not configured. Use 'config --audio-file ...' first.",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)

    if not Path(audio_file_path).exists():
        print(f"Error: Audio file not found at {audio_file_path}", file=sys.stderr)
        raise typer.Exit(code=1)

    entry = _find_entry_by_index(data["subtitles"], index)

    if not entry:
        print(f"Error: No entry found with index {index}.", file=sys.stderr)
        raise typer.Exit(code=1)

    app_cache_dir = Path(tempfile.gettempdir()) / "acolyte"
    try:
        os.makedirs(app_cache_dir, exist_ok=True)
    except Exception as e:
        print(
            f"Error creating cache directory at {app_cache_dir}: {e}", file=sys.stderr
        )
        raise typer.Exit(code=1)

    base_name = draft_file.name.removesuffix(".srt.draft.json")
    clip_filename = f"{base_name}_clip_{index}.mp3"

    temp_clip_path = app_cache_dir / clip_filename

    if temp_clip_path.exists():
        print(
            json.dumps(
                {
                    "status": "success",
                    "clip_path": str(temp_clip_path),
                    "action": "play",
                    "cache": "hit",
                }
            )
        )
        return

    try:
        start_seconds = entry["start_seconds"]
        end_seconds = entry["end_seconds"]
        duration = end_seconds - start_seconds

        (
            ffmpeg.input(audio_file_path, ss=start_seconds)
            .output(
                str(temp_clip_path),
                t=duration,
                format="mp3",
            )
            .run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
        )

    except ffmpeg.Error as e:
        print(
            f"Error processing audio with ffmpeg: {e.stderr.decode()}", file=sys.stderr
        )
        print(
            "Ensure 'ffmpeg' is installed and accessible in your system's PATH.",
            file=sys.stderr,
        )
        raise typer.Exit(code=1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        raise typer.Exit(code=1)

    print(
        json.dumps(
            {
                "status": "success",
                "clip_path": str(temp_clip_path),
                "action": "play",
                "cache": "miss",
            }
        )
    )


if __name__ == "__main__":
    app()
