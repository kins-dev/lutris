"""Misc widgets used in the GUI."""
# Standard Library
import os

from gettext import gettext as _
from enum import Flag, auto

# Third Party Libraries
from gi.repository import GObject, Gtk, Pango

# Lutris Modules
from lutris.gui.widgets.utils import get_stock_icon
from lutris.gui.widgets.default_path import default_path_handler, PATH_TYPE
from lutris.util import system
from lutris.util.linux import LINUX_SYSTEM
from lutris.util.log import logger


class SlugEntry(Gtk.Entry, Gtk.Editable):

    def do_insert_text(self, new_text, length, position):
        """Filter inserted characters to only accept alphanumeric and dashes"""
        new_text = "".join([c for c in new_text if c.isalnum() or c == "-"]).lower()
        length = len(new_text)
        self.get_buffer().insert_text(position, new_text, length)
        return position + length


class NumberEntry(Gtk.Entry, Gtk.Editable):

    def do_insert_text(self, new_text, length, position):
        """Filter inserted characters to only accept numbers"""
        new_text = "".join([c for c in new_text if c.isnumeric()])
        if new_text:
            self.get_buffer().insert_text(position, new_text, length)
            return position + length
        return position


class FileChooserWarnings(Flag):
    NONE = 0
    NON_EMPTY = auto()
    NTFS = auto()


class FileChooserEntry(Gtk.Box):

    """Editable entry with a file picker button"""

    max_completion_items = 15  # Maximum number of items to display in the autocompletion dropdown.

    """
        Parameters
        ----------
        title : str

            Shown on the title of the dialog

        action : Gtk.FileChooserAction

            Show the user select a file(default) or folder
            (https://developer.gnome.org/gtk3/stable/GtkFileChooser.html#GtkFileChooserAction)

        path_type: lutris.gui.widgets.default_path.PATH_TYPE

            UNKNOWN (default) or some explict type of path
            see lutris.gui.widgets.default_path.default_path_handler.get for rules
        path : str
            None (default) or the file/folder the dialog should point to
        default_path : str
            None (default) or where the widget should point by default
        install_path : str
            None (default) or where games should be installed
        game : lutris.game
            None (default) or the game object
        warnings : lutris.gui.widgets.common.FileChooserWarnings
            FileChooserWarnings.NONE (default) or a set of warnings with boolean operations
            This is a Flags enum
        """

    def __init__(
        self,
        title=_("Select file"),
        action=Gtk.FileChooserAction.OPEN,
        path=None,
        path_type=PATH_TYPE.UNKNOWN,
        default_path=None,
        install_path=None,
        game=None,
        warnings=FileChooserWarnings.NONE
    ):

        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            visible=True
        )
        self.title = title
        self.action = action
        self.path = os.path.expanduser(path) if path else None
        self.default_path = os.path.expanduser(default_path) if default_path else None
        self.warn_if_non_empty = bool(warnings & FileChooserWarnings.NON_EMPTY)
        self.warn_if_ntfs = bool(warnings & FileChooserWarnings.NTFS)

        self.path_completion = Gtk.ListStore(str)

        self.entry = Gtk.Entry(visible=True)
        self.entry.set_completion(self.get_completion())
        self.entry.connect("changed", self.on_entry_changed)
        self.path_type = path_type
        self.install_path = install_path
        self.game = game
        if path:
            self.entry.set_text(path)

        browse_button = Gtk.Button(_("Browse..."), visible=True)
        browse_button.connect("clicked", self.on_browse_clicked)

        box = Gtk.Box(spacing=6, visible=True)
        box.pack_start(self.entry, True, True, 0)
        box.add(browse_button)
        self.pack_start(box, False, False, 0)

    def get_text(self):
        """Return the entry's text"""
        return self.entry.get_text()

    def get_filename(self):
        """Deprecated"""
        logger.warning("Just use get_text")
        return self.get_text()

    def get_completion(self):
        """Return an EntryCompletion widget"""
        completion = Gtk.EntryCompletion()
        completion.set_model(self.path_completion)
        completion.set_text_column(0)
        return completion

    def get_filechooser_dialog(self):
        """Return an instance of a FileChooserDialog configured for this widget"""
        dialog = Gtk.FileChooserDialog(title=self.title, transient_for=None, action=self.action)
        dialog.add_buttons(_("_Cancel"), Gtk.ResponseType.CLOSE, _("_OK"), Gtk.ResponseType.OK)
        dialog.set_create_folders(True)
        dialog.connect("response", self.on_select_file)
        return dialog

    def on_browse_clicked(self, _widget):
        """Browse button click callback"""
        file_chooser_dialog = self.get_filechooser_dialog()

        try:
            main_file_path = self.game.runner.get_main_file()
        except AttributeError:
            main_file_path = None

        def_path = default_path_handler.get(
            entry=self.get_text(),
            default=self.default_path,
            main_file_path=main_file_path,
            install_path=self.install_path,
            path_type=self.path_type)

        if os.path.isfile(def_path):
            if self.action != Gtk.FileChooserAction.SELECT_FOLDER:
                file_chooser_dialog.select_filename(def_path)
            else:
                def_path = os.path.dirname(def_path)
                file_chooser_dialog.set_current_folder(def_path)
        else:
            file_chooser_dialog.set_current_folder(def_path)

        file_chooser_dialog.run()

    def on_entry_changed(self, widget):
        """Entry changed callback"""
        self.clear_warnings()
        path = widget.get_text()
        if not path:
            return
        path = os.path.expanduser(path)
        self.update_completion(path)
        if self.warn_if_ntfs and LINUX_SYSTEM.get_fs_type_for_path(path) == "ntfs":
            ntfs_box = Gtk.Box(spacing=6, visible=True)
            warning_image = Gtk.Image(visible=True)
            warning_image.set_from_pixbuf(get_stock_icon("dialog-warning", 32))
            ntfs_box.add(warning_image)
            ntfs_label = Gtk.Label(visible=True)
            ntfs_label.set_markup(_(
                "<b>Warning!</b> The selected path is located on a drive formatted by Windows.\n"
                "Games and programs installed on Windows drives usually <b>don't work</b>."
            ))
            ntfs_box.add(ntfs_label)
            self.pack_end(ntfs_box, False, False, 10)
        if self.warn_if_non_empty and os.path.exists(path) and os.listdir(path):
            non_empty_label = Gtk.Label(visible=True)
            non_empty_label.set_markup(_(
                "<b>Warning!</b> The selected path "
                "contains files. Installation might not work properly."
            ))
            self.pack_end(non_empty_label, False, False, 10)
        parent = system.get_existing_parent(path)
        if parent is not None and not os.access(parent, os.W_OK):
            non_writable_destination_label = Gtk.Label(visible=True)
            non_writable_destination_label.set_markup(_(
                "<b>Warning</b> The destination folder "
                "is not writable by the current user."
            ))
            self.pack_end(non_writable_destination_label, False, False, 10)

    def on_select_file(self, dialog, response):
        """FileChooserDialog response callback"""
        if response == Gtk.ResponseType.OK:
            target_path = dialog.get_filename()
            if target_path:
                dialog.set_current_folder(target_path)
                self.entry.set_text(system.reverse_expanduser(target_path))
            default_path_handler.set_selected(self.entry.get_text(), self.path_type)
        dialog.hide()

    def update_completion(self, current_path):
        """Update the auto-completion widget with the current path"""
        self.path_completion.clear()

        if not os.path.exists(current_path):
            current_path, filefilter = os.path.split(current_path)
        else:
            filefilter = None

        if os.path.isdir(current_path):
            index = 0
            for filename in sorted(os.listdir(current_path)):
                if filename.startswith("."):
                    continue
                if filefilter is not None and not filename.startswith(filefilter):
                    continue
                self.path_completion.append([os.path.join(current_path, filename)])
                index += 1
                if index > self.max_completion_items:
                    break

    def clear_warnings(self):
        """Delete all the warning labels from the container"""
        for index, child in enumerate(self.get_children()):
            if index > 0:
                child.destroy()


class Label(Gtk.Label):

    """Standardised label for config vboxes."""

    def __init__(self, message=None):
        """Custom init of label."""
        super().__init__(label=message)
        self.set_line_wrap(True)
        self.set_max_width_chars(22)
        self.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.set_size_request(230, -1)
        self.set_alignment(0, 0.5)
        self.set_justify(Gtk.Justification.LEFT)


class InstallerLabel(Gtk.Label):

    """Label for installer window"""

    def __init__(self, message=None):
        super().__init__(label=message)
        self.set_max_width_chars(80)
        self.set_property("wrap", True)
        self.set_use_markup(True)
        self.set_selectable(True)
        self.set_alignment(0.5, 0)


class VBox(Gtk.Box):

    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, margin_top=18, **kwargs)


class EditableGrid(Gtk.Grid):
    __gsignals__ = {"changed": (GObject.SIGNAL_RUN_FIRST, None, ())}

    def __init__(self, data, columns):
        self.columns = columns
        super().__init__()
        self.set_column_homogeneous(True)
        self.set_row_homogeneous(True)
        self.set_row_spacing(10)
        self.set_column_spacing(10)

        self.liststore = Gtk.ListStore(str, str)
        for item in data:
            self.liststore.append([str(value) for value in item])

        self.treeview = Gtk.TreeView.new_with_model(self.liststore)
        self.treeview.set_grid_lines(Gtk.TreeViewGridLines.BOTH)
        for i, column_title in enumerate(self.columns):
            renderer = Gtk.CellRendererText()
            renderer.set_property("editable", True)
            renderer.connect("edited", self.on_text_edited, i)

            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            column.set_resizable(True)
            column.set_min_width(100)
            column.set_sort_column_id(0)
            self.treeview.append_column(column)

        self.buttons = []
        self.add_button = Gtk.Button(_("Add"))
        self.buttons.append(self.add_button)
        self.add_button.connect("clicked", self.on_add)

        self.delete_button = Gtk.Button(_("Delete"))
        self.buttons.append(self.delete_button)
        self.delete_button.connect("clicked", self.on_delete)

        self.scrollable_treelist = Gtk.ScrolledWindow()
        self.scrollable_treelist.set_vexpand(True)
        self.scrollable_treelist.add(self.treeview)

        self.attach(self.scrollable_treelist, 0, 0, 5, 5)
        self.attach(self.add_button, 5 - len(self.buttons), 6, 1, 1)
        for i, button in enumerate(self.buttons[1:]):
            self.attach_next_to(button, self.buttons[i], Gtk.PositionType.RIGHT, 1, 1)
        self.show_all()

    def on_add(self, widget):  # pylint: disable=unused-argument
        self.liststore.append(["", ""])
        row_position = len(self.liststore) - 1
        self.treeview.set_cursor(row_position, None, False)
        self.treeview.scroll_to_cell(row_position, None, False, 0.0, 0.0)
        self.emit("changed")

    def on_delete(self, widget):  # pylint: disable=unused-argument
        selection = self.treeview.get_selection()
        _, iteration = selection.get_selected()
        self.liststore.remove(iteration)
        self.emit("changed")

    def on_text_edited(self, widget, path, text, field):  # pylint: disable=unused-argument
        self.liststore[path][field] = text.strip()  # pylint: disable=unsubscriptable-object
        self.emit("changed")

    def get_data(self):  # pylint: disable=arguments-differ
        model_data = []
        for row in self.liststore:  # pylint: disable=not-an-iterable
            model_data.append(row)
        return model_data
