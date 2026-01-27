from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, TextArea, Label
from textual.binding import Binding

from engine import SubtitleManager, SubtitlePair


class SubtitleBlock(Container):
    """
    Widget composto por Label (tempo) e TextArea (conteúdo).
    """

    def __init__(self, id_prefix: str, read_only: bool = True):
        self.time_id = f"{id_prefix}_time"
        self.text_id = f"{id_prefix}_text"
        self.read_only = read_only
        super().__init__(id=id_prefix)

    def compose(self) -> ComposeResult:
        yield Label("--:--:-- --> --:--:--", id=self.time_id)
        yield TextArea(read_only=self.read_only, id=self.text_id)

    def set_content(self, subtitle):
        """
        Atualiza o texto e o tempo e define a cor de borda.
        """
        lbl = self.query_one(f"#{self.time_id}", Label)
        txt = self.query_one(f"#{self.text_id}", TextArea)

        # Limpeza do estado anterior
        self.remove_class("empty", "completed")

        if subtitle:
            # Formatação do tempo
            start = str(subtitle.start).split(".")[0]
            end = str(subtitle.end).split(".")[0]
            lbl.update(f"{start} --> {end}")

            if txt.text != subtitle.content:
                txt.load_text(subtitle.content)

            has_content = len(subtitle.content.strip()) > 0

            if has_content:
                self.add_class("completed")
            else:
                self.add_class("empty")

        else:
            lbl.update("")
            txt.load_text("")
            self.add_class("empty")


class SrtTranslatorApp(App):
    CSS_PATH = "tui.tcss"

    BINDINGS = [
        Binding("ctrl+s", "save_file", "Salvar", priority=True),
        Binding("ctrl+q", "quit", "Sair", priority=True),
        Binding("ctrl+j", "next_subtitle", "Próxima", priority=True),
        Binding("ctrl+k", "prev_subtitle", "Anterior", priority=True),
        Binding("ctrl+h", "edit_original", "Editar Original", priority=True),
        Binding("ctrl+l", "edit_translation", "Editar Tradução", priority=True),
    ]

    def __init__(self, original_path: str, trans_path: str = None):
        super().__init__()
        self.manager = SubtitleManager(
            original_path=original_path, translation_path=trans_path
        )

    def compose(self) -> ComposeResult:
        yield Header()

        # --- Linha anterior (read only) ---
        yield SubtitleBlock("prev_orig", read_only=True)
        yield SubtitleBlock("prev_trans", read_only=True)

        # --- Linha atuál (editável) ---
        yield SubtitleBlock("current_orig", read_only=False)
        yield SubtitleBlock("current_trans", read_only=False)

        # --- Próxima linha (read only) ---
        yield SubtitleBlock("next_orig", read_only=True)
        yield SubtitleBlock("next_trans", read_only=True)

        yield Footer()

    def on_mount(self):
        self.title = "SRT TRANSLATOR TUI"
        self.update_view()
        self.query_one("#current_trans_text", TextArea).focus()

    def update_view(self):
        prev_sub, current_sub, next_sub = self.manager.get_view_window()

        self.query_one("#prev_orig", SubtitleBlock).set_content(
            prev_sub.original if prev_sub else None
        )
        self.query_one("#prev_trans", SubtitleBlock).set_content(
            prev_sub.translated if prev_sub else None
        )

        self.query_one("#current_orig", SubtitleBlock).set_content(current_sub.original)
        self.query_one("#current_trans", SubtitleBlock).set_content(
            current_sub.translated
        )

        self.query_one("#next_orig", SubtitleBlock).set_content(
            next_sub.original if next_sub else None
        )
        self.query_one("#next_trans", SubtitleBlock).set_content(
            next_sub.translated if next_sub else None
        )

        idx = current_sub.original.index
        total = len(self.manager.pairs)
        self.sub_title = f"Legenda {idx} de {total}"

    def on_text_area_changed(self, event: TextArea.Changed):
        """
        Detecta digitação e salva na memória em tempo real.
        """
        ctrl_id = event.text_area.id

        if ctrl_id == "current_trans_text":
            self.manager.update_current_translation(event.text_area.text)
            parent = self.query_one("#current_trans", SubtitleBlock)
            if event.text_area.text.strip():
                parent.add_class("completed")
                parent.remove_class("empty")
            else:
                parent.add_class("empty")
                parent.remove_class("completed")

        elif ctrl_id == "current_orig_text":
            self.manager.update_current_original(event.text_area.text)

    def action_next_subtitle(self):
        self.manager.next_subtitle()
        self.update_view()

    def action_prev_subtitle(self):
        self.manager.prev_subtitle()
        self.update_view()

    def action_save_file(self):
        self.manager.save()
        self.notify(
            "Arquivo salvo com sucesso!", title="Salvar", severity="information"
        )

    def action_edit_original(self):
        self.query_one("#current_orig_text", TextArea).focus()
        self.notify("Editando original. CTRL + L para voltar.")

    def action_edit_translation(self):
        self.query_one("#current_trans_text", TextArea).focus()


if __name__ == "__main__":
    import sys

    # Exemplo de uso: python tui.py filme.srt
    if len(sys.argv) < 2:
        print("Uso: python tui.py <arquivo_original.srt> [arquivo_traducao.srt]")
    else:
        orig = sys.argv[1]
        trans = sys.argv[2] if len(sys.argv) > 2 else None

        app = SrtTranslatorApp(orig, trans)
        app.run()
