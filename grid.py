import itertools
import types
from array import array
from typing import Sequence, NamedTuple, Any, overload
from dearpygui import dearpygui as dpg
from dearpygui._dearpygui import (
    get_item_state,
    get_item_configuration,
    configure_item,
)

__all__ = [
    "get_item_rect",
    "set_item_rect",
    "Point",
    "Rect",
    "Grid",
]


class Point(NamedTuple):
    x: float
    y: float


class Rect(NamedTuple):
    x     : float
    y     : float
    width : float
    height: float


def get_item_rect(item: int) -> Rect:
    # `rect_size` is unreliable for debugging, so get the width and height
    # instead. Using `rect_size` instead would only spare a function call.
    pos = get_item_state(item)["pos"]
    config = get_item_configuration(item)
    return Rect(*pos, config["width"], config["height"])


def set_item_rect(
    item: int,
    x_pos: float,
    y_pos: float,
    width: float,
    height: float,
) -> None:
    # Unfortunately, DPG only accepts integers. There will almost always
    # be a slight inaccuracy due to the conversion.
    # TODO: Maybe use `round` instead? `int` will always use the floor.
    configure_item(
        item,
        pos=(int(x_pos),int(y_pos)),
        width=int(width),
        height=int(height),
    )


class Weights(array):
    def __new__(cls, length: int):
        return array.__new__(cls, "f", itertools.repeat(1.0, length))

    def __init__(self, length: int):
        array.__init__(self)

    def sum(self) -> float:
        return sum(self)

    def resize(self, amount: int) -> None:
        current_length = self.__len__()
        if amount >= current_length:
            self.extend(itertools.repeat(1.0, amount))
        else:
            del self[-1: amount -1: -1]  # trim in-place


class Grid:
    """A layout manager for DearPyGui. Aligns items in a virtual table-like structure.

    Properties
        * target [get]
        * items [get]
        * rows [get, set]
        * cols [get, set]
        * spacing [get, set]
        * padding [get, set]
        * row_weights [get]
        * col_weights [get]
    """

    __slots__ = (
        "items",
        "_items",
        "_target",
        "_spacing",
        "_padding",
        "_row_weights",
        "_col_weights",
    )

    def __init__(self, target: int | str, *, cols: int = 1, rows: int = 1, spacing: Point = (0, 0), padding: Point = (0, 0)):
        """Args:
            * target (int | str): The item to scale the grid to. It must have a valid rect (i.e.
            position, width, height).

            * cols (int, optional): The number of columns in the grid. Cannot be set below 1.
            Defaults to 1.

            * rows (int, optional): The number of rowss in the grid. Cannot be set below 1. Defaults
            to 1.

            * spacing (Point, optional): The horizontal and vertical space between cells. Defaults
            to (0, 0).

            * padding (Point, optional): The horizontal and vertical space between the target item's
            bounding box and an outer cell. Defaults to (0, 0).
        """
        if rows < 1:
            raise ValueError("Requires at least 1 row.")
        if cols < 1:
            raise ValueError("Requires at least 1 column.")
        self._target     : int            = target
        self._row_weights: Weights[float] = Weights(rows)  # x axis
        self._col_weights: Weights[float] = Weights(cols)  # y axis
        self._spacing    : Point          = Point(*spacing)
        self._padding    : Point          = Point(*padding)

        self._items: dict[int | str, tuple[Point, Point]] = {}
        self.items = types.MappingProxyType(self._items)

    @overload
    def __getitem__(self, index: int) -> tuple[int | None, ...]: ...
    @overload
    def __getitem__(self, index: tuple[int, int]) -> int | None: ...
    def __getitem__(self, index):
        # `self[x]` will return all items in the row
        # `self[x, y]` will return an item at a specific cell or None
        if isinstance(index, tuple) and len(index) == 2:
            return self.get_item(*index)
        elif isinstance(index, int):
            items = [item for item, (coords, _) in self._items.items()
                    if index == coords[0]].sort(key=lambda x: x[1])
            return tuple(items)
        raise IndexError(*index)

    def __setitem__(self, index: tuple[int, int], item: int) -> None:
        if not isinstance(index, tuple) and len(index) != 2:
            return NotImplemented
        self.place(item, *index)

    @property
    def target(self) -> int | str:
        """[get]: The item that the grid scales to."""
        return self._target

    @property
    def rows(self) -> int:
        """[get, set]: The number of rows in the grid. Cannot be set below 1.
        Zero-indexed.
        """
        return self._row_weights.__len__()
    @rows.setter
    def rows(self, value: int) -> None:
        self.configure(rows=value)

    @property
    def cols(self) -> int:
        """[get, set]: The number of columns in the grid. Cannot be set below 1.
        Zero-indexed.
        """
        return self._col_weights.__len__()
    @cols.setter
    def cols(self, value: int) -> None:
        self.configure(cols=value)

    @property
    def spacing(self) -> Point:
        """[get, set]: The horizontal and vertical space between cells."""
        return self._spacing
    @spacing.setter
    def spacing(self, value: tuple[int, int]) -> None:
        self.configure(spacing=value)

    @property
    def padding(self) -> Point:
        """[get, set]: The horizontal and vertical space between the target item's
        bounding box and an outer cell.
        """
        return self._padding
    @padding.setter
    def padding(self, value: tuple[int, int]) -> None:
        self.configure(padding=value)

    @property
    def row_weights(self) -> tuple[float]:
        """[get]: A list containing the weight of each row. Each new row is
        assigned a weight of 1.
        """
        return tuple(self._row_weights)

    @property
    def col_weights(self) -> tuple[float]:
        """[get]: A list containing the weight of each column. Each new column is
        assigned a weight of 1.
        """
        return tuple(self._col_weights)

    def set_row_weight(self, index: int, weight: float) -> None:
        """Configure a row's weight value. Ignored if *weight* is negative."""
        self.configure(row_weights=((index, weight),))

    def set_col_weight(self, index: int, weight: float) -> None:
        """Configure a column's weight value. Ignored if *weight* is negative."""
        self.configure(col_weights=((index, weight),))

    def configure(
        self,
        *,
        rows       : int                         = 0,
        cols       : int                         = 0,
        row_weights: Sequence[tuple[int, float]] = (),
        col_weights: Sequence[tuple[int, float]] = (),
        padding    : tuple[int, int]             = (),
        spacing    : tuple[int, int]             = (),
    ) -> None:
        """Update the grid's settings.

        Args:
            * rows (int, optional): The number of rows in the grid. A value below 1
            is ignored.

            * cols (int, optional): The number of rows in the grid. A value below 1
            is ignored.

            * row_weights (Sequence[tuple[int, float]], optional): 2-tuples containing the
            index of an existing row and a weight value. A pair is ignored if the weight
            value is negative.

            * col_weights (Sequence[tuple[int, float]], optional): 2-tuples containing the
            index of an existing column and a weight value. A pair is ignored if the weight
            value is negative.

            * padding (tuple[int, int], optional): The horizontal and vertical space between
            cells.

            * spacing (tuple[int, int], optional): The horizontal and vertical space between
            the target item's bounding box and an outer cell.
        """
        # grid size
        if rows > 0:
            self._row_weights.resize(rows - len(self._row_weights))
        if cols > 0:
            self._row_weights.resize(cols - len(self._col_weights))
        # weights
        for _idx, _weight in row_weights:
            if _weight > 0:
                self._row_weights[_idx] = _weight
        for _idx, _weight in col_weights:
            self._col_weights[_idx] = _weight
        # alignment
        if padding:
            self._padding = Point(*padding)
        if spacing:
            self._spacing = Point(*spacing)
        self.redraw()

    def configuration(self) -> dict[str, Any]:
        """Return a copy of the grid's settings."""
        return {
            "rows"       : self.rows,
            "cols"       : self.cols,
            "row_weights": self.row_weights,
            "col_weights": self.col_weights,
            "spacing"    : self.spacing,
            "padding"    : self.padding,
        }

    def redraw(self, *args, **kwargs) -> None:
        """Force the grid to recalculate the positions and sizes of all items
        managed by the grid.

        Ideally, this should be passed as a resize callback for the target item
        or viewport.
        """
        # TODO: This will probably need optimizing.
        get_cell_rect = self._get_cell_rect
        for item, (start_cell, stop_cell) in self._items.items():
            x_pos, y_pos, width, height = get_cell_rect(*start_cell)
            if stop_cell:
                stop_cell_rect = get_cell_rect(*stop_cell)
                width  = stop_cell_rect[0] + stop_cell_rect[2] - x_pos
                height = stop_cell_rect[1] + stop_cell_rect[3] - y_pos
            set_item_rect(item, x_pos, y_pos, width, height)

    def get_item(self, row: int, col: int) -> int | str | None:
        """Return the first item found in the grid at `(*row*, *col*)`, or None if the cell
        is empty.
        """
        index = row, col
        for item, (coords, _) in self._items.items():
            if coords == index:
                return item
        # No item at index -- check if the indexes are valid.
        try:
            self._row_weights[row]
            self._col_weights[col]
        except IndexError:
            raise IndexError(row, col) from None
        return None

    def get_cell(self, item: int) -> tuple[int, int]:
        """Return the cell coordinates of an item managed by the grid."""
        return self._items[item][0]

    def clear(self) -> None:
        """De-couple all items from the grid. Their current positions will be
        unchanged, but will not be managed further."""
        self._items.clear()

    def clear_item(self, item: int) -> None:
        """De-couple an item from the grid. It's current position will be
        unchanged, but will not be managed further.
        """
        self._items.pop(item, None)

    def position(self, item: int, x: float = 0, y: float = 0):
        """Place an item anywhere on the grid. Its position will not be managed.
        """
        configure_item(item, pos=(int(x), int(y)))

    def place(self, item: int, row: int, col: int, *, rowspan: int = 0, colspan: int = 0):
        """Add an item to be manged by the grid and position it in a cell.

        Args:
            * item (int): Identifier for an item. It must have a valid rect (i.e.
            position, width, height). To make other items compatible, consider
            altering or redefining `get_item_rect`.

            * row (int): The target row's index (zero-indexed). A positive index starts
            from the first row while a negative index starts from the last row.

            * col (int): The target column's index (zero-indexed). A positive index starts
            from the first column while a negative index starts from the last column.

            * rowspan (int): The number of additional rows that the item will occupy.
            Defaults to 0.

            * colspan (int): The number of additional columns that the item will occupy.
            Defaults to 0.
        """
        if rowspan < 0 or colspan < 0:
            raise ValueError("`rowspan`/`colspan` must be positive.")
        stop_cell_row = row + rowspan
        if stop_cell_row + 1 > len(self._row_weights):
            raise IndexError("`row` outside of index range pre/post `rowspan`.")
        stop_cell_col = col + colspan
        if stop_cell_col + 1 > len(self._col_weights):
            raise IndexError("`col` outside of index range pre/post `colspan`.")

        start_cell_rect = self._get_cell_rect(row, col)
        if rowspan or colspan:
            stop_cell_rect = self._get_cell_rect(stop_cell_row, stop_cell_col)
            width  = stop_cell_rect[0] + stop_cell_rect[2] - start_cell_rect[0]
            height = stop_cell_rect[1] + stop_cell_rect[3] - start_cell_rect[1]
            self._items[item] = ((row, col), (stop_cell_row, stop_cell_col))
        else:
            width  = start_cell_rect[2]
            height = start_cell_rect[3]
            self._items[item] = ((row, col), ())
        set_item_rect(item, start_cell_rect[0], start_cell_rect[1], width, height)


    #### INTERNAL METHODS ####
    def _get_content_rect(self) -> Rect:
        """Return the position and size of the grid target's content region."""
        rect = get_item_rect(self._target)
        x_padding, y_padding = self._padding
        return Rect(
            x_padding,
            y_padding,
            rect[2] - x_padding - x_padding,
            rect[3] - y_padding - y_padding,
        )

    def _get_cell_rect(self, row: int, col: int) -> Rect:
        """Return the position and size of a cell's content region."""
        x_pos, y_pos, cont_width, cont_height = self._get_content_rect()
        x_weight = self._col_weights.sum()
        y_weight = self._row_weights.sum()
        wt_per_weight = cont_width / x_weight
        ht_per_weight = cont_height / y_weight

        x_spacing, y_spacing = self._spacing
        x_cell_pad    = x_spacing / 2
        y_cell_pad    = y_spacing / 2
        x_cell_weight = self._col_weights[col]
        y_cell_weight = self._row_weights[row]

        # cell position
        # NOTE: To keep this simple, the rect for all cells (even the first
        # cell per row/column) will be adjusted to account for cell spacing.
        cell_x_pos  = x_pos + x_cell_pad
        cell_x_pos += wt_per_weight * sum(self._col_weights[0:col])
        cell_y_pos  = y_pos + y_cell_pad
        cell_y_pos += ht_per_weight * sum(self._row_weights[0:row])
        # cell size
        cell_width  = wt_per_weight * x_cell_weight - x_spacing
        cell_height = ht_per_weight * y_cell_weight - y_spacing

        return Rect(cell_x_pos, cell_y_pos, cell_width, cell_height)



if __name__ == '__main__':
    dpg.create_context()
    dpg.create_viewport(width=400, height=400)
    dpg.setup_dearpygui()

    with dpg.theme() as theme:
        with dpg.theme_component(0):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (200, 200, 0, 50))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (200, 200, 0, 255))
    dpg.bind_theme(theme)

    with dpg.window(width=400, height=400, no_scrollbar=True, no_background=True) as win:
        btn1 = dpg.add_button(label=1)
        btn2 = dpg.add_button(label=2)
        btn3 = dpg.add_button(label=3)
        btn4 = dpg.add_button(label=4)
        btn5 = dpg.add_button(label=5)

        grid = Grid(win, cols=2, rows=4, padding=(40, 0))
        grid.set_row_weight(1, 3)
        grid.place(btn1, 0, 0, rowspan=2, colspan=0)
        grid.place(btn2, 1, 1)
        grid.place(btn3, 2, 0, colspan=1)
        grid.place(btn4, 0, 1, rowspan=1)
        grid.place(btn5, -1, 0, colspan=1)


    def resize_callback():
        grid.redraw()

    dpg.set_primary_window(win, True)
    dpg.set_viewport_resize_callback(resize_callback)
    dpg.show_viewport()
    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()