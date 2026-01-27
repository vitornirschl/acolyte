import srt
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class SubtitlePair:
    original: srt.Subtitle
    translated: srt.Subtitle


class SubtitleManager:
    def __init__(self, original_path: str, translation_path: Optional[str] = None):
        self.original_path = original_path
        self.translation_path = translation_path or original_path.replace(
            ".srt", "_pt.srt"
        )

        # Carrega as legendas
        self.pairs: List[SubtitlePair] = self._load_and_merge()

        # Índice do cursor (que leganda estamos editando agora)
        self.current_index = 0

    def _load_and_merge(self) -> List[SubtitlePair]:
        """
        Lê o arquivo original e o de tradução (se ele existir).
        Se o arquivo de tradução nao existir ou se tiver menos índices que o original,
        cria entradas vazias com base no original.
        """
        # Leitura do original
        with open(self.original_path, "r", encoding="utf-8") as f:
            originals = list(srt.parse(f.read()))

        translated_map = {}
        if self.translation_path:
            try:
                with open(self.translation_path, "r", encoding="utf-8") as f:
                    translations = list(srt.parse(f.read()))
                    translated_map = {sub.index: sub for sub in translations}
            except FileNotFoundError:
                pass

        merged_pairs = []
        for orig in originals:
            if orig.index in translated_map:
                trans = translated_map[orig.index]
            else:
                trans = srt.Subtitle(
                    index=orig.index, start=orig.start, end=orig.end, content=""
                )

            merged_pairs.append(SubtitlePair(original=orig, translated=trans))

        return merged_pairs

    def get_view_window(
        self,
    ) -> Tuple[Optional[SubtitlePair], SubtitlePair, Optional[SubtitlePair]]:
        """
        Retorna as legendas anterior, atual e posterior.
        """
        prev_sub = (
            self.pairs[self.current_index - 1] if self.current_index > 0 else None
        )
        current_sub = self.pairs[self.current_index]
        next_sub = (
            self.pairs[self.current_index + 1]
            if self.current_index < len(self.pairs) - 1
            else None
        )

        return prev_sub, current_sub, next_sub

    def update_current_translation(self, new_text: str):
        """
        Edita o texto da tradução no bloco atual.
        """
        self.pairs[self.current_index].translated.content = new_text

    def update_current_original(self, new_text: str):
        """
        Edita o texto original no bloco atual.
        """
        self.pairs[self.current_index].original.content = new_text

    def next_subtitle(self):
        if self.current_index < len(self.pairs) - 1:
            self.current_index += 1

    def prev_subtitle(self):
        if self.current_index > 0:
            self.current_index -= 1

    def save(self, overwrite_original: Optional[bool] = True):

        trans_subs = [pair.translated for pair in self.pairs]
        output_trans = srt.compose(trans_subs)

        with open(self.translation_path, "w", encoding="utf-8") as f:
            f.write(output_trans)

        if overwrite_original:
            original_subs = [pair.original for pair in self.pairs]
            output_original = srt.compose(original_subs)

            with open(self.original_path, "w", encoding="utf-8") as f:
                f.write(output_original)
