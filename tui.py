from textual.app import App, ComposeResult
from textual.containers import Container, Grid, Center
from textual.widgets import Header, Footer, ProgressBar, TextArea, Label
from textual.binding import Binding
from engine import TranslationManager
from typing import Optional


class SubtitleBlock(Container):
    """
    Widget para bloco de legenda.
    Composto por Label (tempo) e TextArea (conteúdo).
    """

    def __init__(self, id_prefix: str, read_only: bool = True, **kwargs):
        self.time_id = f"{id_prefix}_time"
        self.text_id = f"{id_prefix}_text"
        self.read_only = read_only
        super().__init__(id=id_prefix, **kwargs)

    def compose(self) -> ComposeResult:
        yield Label("--:--:-- --> --:--:--", id=self.time_id)
        yield TextArea(read_only=self.read_only, id=self.text_id)

    def set_content(self, subtitle):
        """
        Atualiza as informações do bloco de legenda.
        """
        lbl = self.query_one(f"#{self.time_id}", Label)
        txt = self.query_one(f"#{self.text_id}", TextArea)

        # Limpeza de estado
        self.remove_class("empty", "verified", "unverified")

        if subtitle:
            # atualiza timestamp
            start = str(subtitle.start).split(".")[0]
            end = str(subtitle.end).split(".")[0]
            lbl.update(f"{start} --> {end}")

            # atualiza texto
            if txt.text != subtitle.content:
                txt.load_text(subtitle.content)

                has_content = len(subtitle.content.strip()) > 0

                # atualiza status
                if has_content:
                    self.add_class("verified")
                else:
                    self.add_class("empty")

        else:
            lbl.update("")
            txt.load_text("")
            self.add_class("empty")


class Acolyte(App):
    CSS_PATH = "tui.tcss"

    BINDINGS = [
        Binding("ctrl+s", "save", "Salvar", priority=True),
        Binding("ctrl+q", "quit", "Sair", priority=True),
        Binding("ctrl+j", "next_subtitle", "Próxima", priority=True),
        Binding("ctrl+k", "prev_subtitle", "Anterior", priority=True),
        Binding("ctrl+h", "edit_original", "Editar Original", priority=True),
        Binding("ctrl+l", "edit_translation", "Editar Tradução", priority=True),
        Binding("ctrl+space", "play_media", "Tocar Mídia", priority=True),
        Binding("ctrl+r", "toggle_status", "Alternar Status", priority=True),
    ]

    def __init__(
        self,
        original_path: Path | str,
        translated_path: Optional[Path | str] = None,
        status_path: Optional[Path | str] = None,
        media_path: Optional[Path | str] = None,
    ):
        super().__init__()
        self.manager = TranslationManager(
            original_path=original_path,
            translated_path=translated_path,
            status_path=status_path,
            media_path=media_path,
        )

    def compose(self) -> ComposeResult:
        # Cabeçalho
        yield Header()

        # Barra de progresso
        with Center():
            yield Label("Progresso: ")
            yield ProgressBar(total=len(self.manager.pairs), show_eta=False)

        with Grid(id="editor"):
            # Linha anterior
            yield SubtitleBlock(id_prefix="prev_orig", classes="second_plan")
            yield SubtitleBlock(id_prefix="prev_trans", classes="second_plan")

            # Linha atual
            yield SubtitleBlock(id_prefix="curr_orig", read_only=False)
            yield SubtitleBlock(id_prefix="curr_trans", read_only=False)

            # Próxima linha
            yield SubtitleBlock(id_prefix="next_orig", classes="second_plan")
            yield SubtitleBlock(id_prefix="next_trans", classes="second_plan")

        # Rodapé
        yield Footer()

    def update_view(self):
        prev_pair, curr_pair, next_pair = self.manager.get_view_window()

        # Bloco de legendas anteriores
        prev_orig = self.query_one("#prev_orig", SubtitleBlock)
        prev_trans = self.query_one("#prev_trans", SubtitleBlock)
        if prev_pair:
            prev_orig.set_content(prev_pair.original_sub)
            prev_trans.set_content(prev_pair.translated_sub)
            if prev_pair.is_approved:
                prev_trans.add_class("verified")
            else:
                prev_trans.remove_class("verified")
        else:
            prev_orig.set_content(None)
            prev_trans.set_content(None)
            prev_trans.remove_class("verified")

        # Bloco de legendas atuais
        curr_orig = self.query_one("#curr_orig", SubtitleBlock)
        curr_trans = self.query_one("#curr_trans", SubtitleBlock)

        curr_orig.set_content(curr_pair.original_sub)
        curr_trans.set_content(curr_pair.translated_sub)
        if curr_pair.is_approved:
            curr_trans.add_class("verified")
        else:
            curr_trans.remove_class("verified")

        # Bloco das próximas legendas
        next_orig = self.query_one("#next_orig", SubtitleBlock)
        next_trans = self.query_one("#next_trans", SubtitleBlock)
        if next_pair:
            next_orig.set_content(next_pair.original_sub)
            next_trans.set_content(next_pair.translated_sub)
            if next_pair.is_approved:
                next_trans.add_class("verified")
            else:
                next_trans.remove_class("verified")
        else:
            next_orig.set_content(None)
            next_trans.set_content(None)
            next_trans.remove_class("verified")

        count_verified = sum(1 for p in self.manager.pairs if p.is_approved)
        self.query_one(ProgressBar).update(progress=count_verified)

    def on_mount(self):
        self.theme = "dracula"
        self.title = "Acolyte"
        self.subtitle = f"{self.manager.original_path.stem}"

        self.update_view()
        self.query_one("#curr_trans_text", TextArea).focus()

    def on_text_area_changed(self, event: TextArea.Changed):
        """
        Detecta digitação e salva na memória em tempo real.
        """
        txt_area_id = event.text_area.id

        # atualização da tradução
        if txt_area_id == "curr_trans_text":
            # atualização do conteúdo
            self.manager.update_current_translation(event.text_area.text)

            if event.text_area.text.strip():
                self.manager.pairs[self.manager.current_index].is_approved = True
                self.query_one("#curr_trans", SubtitleBlock).add_class("verified")
            else:
                self.manager.pairs[self.manager.current_index].is_approved = False
                self.query_one("#curr_trans", SubtitleBlock).remove_class("verified")

        # atualização do texto original
        elif txt_area_id == "curr_orig_text":
            self.manager.update_current_original(event.text_area.text)

    def action_next_subtitle(self):
        self.manager.next_idx()
        self.update_view()

    def action_prev_subtitle(self):
        self.manager.previous_idx()
        self.update_view()

    def action_play_media(self):
        try:
            self.manager.play_current_segment()
        except FileNotFoundError as e:
            self.notify(str(e), severity="warning", title="Sem mídia disponível")
        except RuntimeError as e:
            self.notify(str(e), severity="error", title="Erro de execução")
        except Exception as e:
            self.notify(str(e), severity="error", title="Erro desconhecido")

    def action_save(self):
        try:
            self.manager.save()
        except Exception as e:
            self.notify(str(e), severity="error", title="Erro ao salvar")
        else:
            self.notify("Salvo com sucesso!", title="Sucesso")

    def action_edit_original(self):
        self.query_one("#curr_orig_text", TextArea).focus()
        self.notify("Editando original. CTRL + L para voltar.")

    def action_edit_translation(self):
        self.query_one("#curr_trans_text", TextArea).focus()

    def action_toggle_status(self):
        # recupera o par de legendas atual do manager
        curr_pair = self.manager.pairs[self.manager.current_index]

        # inverte o status
        curr_pair.is_approved = not curr_pair.is_approved

        # atualiza a barra de progresso
        count_verified = sum(1 for p in self.manager.pairs if p.is_approved)
        self.query_one(ProgressBar).update(progress=count_verified)

        self.update_view()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Uso: python trui.py <arquivo_original.srt> [arquivo_traducao.srt] [arquivo_status.json] [arquivo_media.mp4]"
        )
    else:
        orig = sys.argv[1]
        trans = sys.argv[2] if len(sys.argv) > 2 else None
        status = sys.argv[3] if len(sys.argv) > 3 else None
        media = sys.argv[4] if len(sys.argv) > 4 else None

        app = Acolyte(orig, trans, status, media)
        app.run()
