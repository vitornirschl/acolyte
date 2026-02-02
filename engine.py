from dataclasses import dataclass
from datetime import timedelta
from typing import Optional, List, Dict
from pathlib import Path
import srt
import json
import shutil
import subprocess


@dataclass
class SubtitlePair:
    """
    Representa um par de legendas original / tradução, com seu status.
    """

    index: int  # índice do trecho da transcrição
    start: timedelta  # tempo de início do trecho
    end: timedelta  # tempo de fim do trecho

    original_sub: srt.Subtitle
    translated_sub: srt.Subtitle
    is_approved: bool = False  # status da tradução do trecho


class TranslationManager:
    """
    Gerencia o estado global da tradução.
    """

    def __init__(
        self,
        original_path: Path | str,
        translated_path: Optional[Path | str] = None,
        status_path: Optional[Path | str] = None,
        media_path: Optional[Path | str] = None,
    ):
        self.original_path = Path(original_path)
        self.status_path = (
            Path(status_path)
            if status_path
            else self.original_path.with_name(f"{self.original_path.stem}_status.json")
        )
        self.translated_path = (
            Path(translated_path)
            if translated_path
            else self.original_path.with_name(
                f"{self.original_path.stem}_translation.srt"
            )
        )
        self.media_path = Path(media_path) if media_path else None

        self.pairs: List[SubtitlePair] = (
            []
        )  # lista de pares de trechos original / tradução
        self._load_data()

        self.current_index = 0  # índice do trecho sendo editado

    def _load_data(self):
        with open(self.original_path, "r", encoding="utf-8") as f:
            originals = list(srt.parse(f.read()))

        status_map: Dict[int, bool] = {}  # Mapa {índice: status}

        if self.status_path.exists():
            with open(self.status_path, "r") as f:
                raw_json = json.load(f)
                status_map = {int(k): v for k, v in raw_json.items()}
        else:
            pass

        translated_map = {}  # Mapa {índice: tradução}
        if self.translated_path.exists():
            with open(self.translated_path, "r", encoding="utf-8") as f:
                translations = list(srt.parse(f.read()))
                translated_map = {sub.index: sub for sub in translations}
        else:
            pass

        merged_pairs = []  # Lista dos pares {original / tradução}
        for orig_sub in originals:
            if orig_sub.index in translated_map:
                trans_sub = translated_map.get(orig_sub.index)
            else:
                trans_sub = srt.Subtitle(
                    index=orig_sub.index,
                    start=orig_sub.start,
                    end=orig_sub.end,
                    content="",
                )

            approved = status_map.get(orig_sub.index, False)

            merged_pairs.append(
                SubtitlePair(
                    index=orig_sub.index,
                    start=orig_sub.start,
                    end=orig_sub.end,
                    original_sub=orig_sub,
                    translated_sub=trans_sub,
                    is_approved=approved,
                )
            )

        self.pairs = merged_pairs

    def get_view_window(
        self,
    ) -> tuple[Optional[SubtitlePair], SubtitlePair, Optional[SubtitlePair]]:
        prev_pair = (
            self.pairs[self.current_index - 1] if self.current_index > 0 else None
        )
        curr_pair = self.pairs[self.current_index]
        next_pair = (
            self.pairs[self.current_index + 1]
            if self.current_index < len(self.pairs) - 1
            else None
        )

        return prev_pair, curr_pair, next_pair

    def update_current_original(self, new_text: str):
        self.pairs[self.current_index].original_sub.content = new_text

    def update_current_translation(self, new_text: str):
        self.pairs[self.current_index].translated_sub.content = new_text
        self.validate_current_translation()

    def previous_idx(self):
        self.current_index -= 1 if self.current_index > 0 else 0

    def next_idx(self):
        last_subtitle_index = len(self.pairs) - 1
        self.current_index += 1 if self.current_index < last_subtitle_index else 0

    def validate_current_translation(self):
        self.pairs[self.current_index].is_approved = True

    def play_current_segment(self):
        """
        Toca arquivo de mídia no intervalo de tempo sendo editado.
        """
        if not self.media_path or not self.media_path.exists():
            raise FileNotFoundError(
                "Arquivo de mídia não encontrado ou não configurado."
            )

        pair = self.pairs[self.current_index]
        start = pair.start.total_seconds()
        end = pair.end.total_seconds()

        player_exec = shutil.which("mpv")  # tenta usar o mpv como player
        if not player_exec:
            player_exec = shutil.which("ffplay")  # fallback: ffmpeg
            if not player_exec:
                raise RuntimeError(
                    "ERRO: É necessário instalar 'mpv' ou 'ffmpeg' para rodar o arquivo de mídia."
                )

            # Lógica para ffplay
            duration = end - start
            cmd = [
                player_exec,
                "-ss",
                str(start),
                "-t",
                str(duration),
                "-autoexit",
                "-hide_banner",
                str(self.media_path),
            ]
        else:
            # Lógica para mpv
            cmd = [
                player_exec,
                f"--start={start}",
                f"--end={end}",
                "--force-window=immediate",
                str(self.media_path),
            ]

        subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )  # execução do comando para rodar mídia

    def save(self):
        # Salvar primeiro o status
        status_map = {pair.index: pair.is_approved for pair in self.pairs}
        with open(self.status_path, "w", encoding="utf-8") as f:
            json.dump(status_map, f, indent=2)

        # Salvar o original modificado (sobrescreve) e a tradução
        originals = [pair.original_sub for pair in self.pairs]
        translated = [pair.translated_sub for pair in self.pairs]

        output_originals = srt.compose(originals)
        output_translated = srt.compose(translated)

        with open(self.original_path, "w", encoding="utf-8") as f:
            f.write(output_originals)

        with open(self.translated_path, "w", encoding="utf-8") as f:
            f.write(output_translated)
